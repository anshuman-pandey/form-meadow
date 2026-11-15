"""Versioned form and submission storage. No network or authentication layer."""
import csv
import io
import json
import re
import secrets
import sqlite3
from datetime import datetime, timezone


class FormError(ValueError):
    pass


def bounded(value, name, limit, required=True):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):
        raise FormError(f'{name} must be text, at most {limit} characters.')
    if '\x00' in value:
        raise FormError(f'{name} contains a null character.')
    return value


def definition(value):
    if not isinstance(value,dict) or set(value)-{'title','description','fields'}:
        raise FormError('Unknown form properties.')
    title=bounded(value.get('title'),'Title',200)
    description=bounded(value.get('description',''),'Description',2000,False)
    fields=value.get('fields')
    if not isinstance(fields,list) or not 1<=len(fields)<=30:
        raise FormError('Use between 1 and 30 fields.')
    result=[];seen=set()
    for field in fields:
        if not isinstance(field,dict) or set(field)-{'id','label','type','required','options'}:
            raise FormError('Unknown field properties.')
        key=field.get('id');kind=field.get('type');required=field.get('required',False)
        if not isinstance(key,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',key) or key in seen:
            raise FormError('Field IDs must be unique lowercase identifiers.')
        if kind not in ('text','email','choice','consent') or type(required) is not bool:
            raise FormError('Invalid field type or required flag.')
        label=bounded(field.get('label'),'Label',300)
        options=field.get('options',[])
        if kind=='choice':
            if not isinstance(options,list) or not 2<=len(options)<=30:
                raise FormError('Choice fields need 2 to 30 options.')
            options=[bounded(o,'Option',200) for o in options]
            if len(set(options))!=len(options):raise FormError('Choice options must be unique.')
        elif options:
            raise FormError('Only choice fields have options.')
        result.append(dict(id=key,label=label,type=kind,required=required,options=options));seen.add(key)
    return dict(title=title,description=description,fields=result)


def answers(schema, values):
    if not isinstance(values,dict) or set(values)-{f['id'] for f in schema['fields']}:
        raise FormError('Response contains unknown fields.')
    result={}
    for field in schema['fields']:
        key=field['id'];kind=field['type'];value=values.get(key,False if kind=='consent' else '')
        if kind=='consent':
            if type(value) is not bool or (field['required'] and not value):
                raise FormError(f'{key}: confirm this checkbox.')
        else:
            value=bounded(value,key,4000,field['required'])
            if value and kind=='email' and (len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value)):
                raise FormError(f'{key}: enter an email address.')
            if value and kind=='choice' and value not in field['options']:
                raise FormError(f'{key}: choose a listed option.')
        result[key]=value
    return result


def csv_cell(value):
    value=str(value)
    # Spreadsheet formula interpretation can follow whitespace/control prefixes.
    if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')):
        return "'"+value
    return value


class Forms:
    def __init__(self,path):
        self.db=sqlite3.connect(path,timeout=5)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS forms(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,open INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS versions(form_id TEXT REFERENCES forms(id),revision INTEGER,schema TEXT NOT NULL,PRIMARY KEY(form_id,revision));
          CREATE TABLE IF NOT EXISTS responses(id TEXT PRIMARY KEY,form_id TEXT,revision INTEGER,submitted_at TEXT NOT NULL,answers TEXT NOT NULL,request_key TEXT NOT NULL,
          UNIQUE(form_id,request_key),FOREIGN KEY(form_id,revision) REFERENCES versions(form_id,revision));
        ''')

    def close(self):self.db.close()

    def create(self,schema):
        schema=definition(schema);key=secrets.token_urlsafe(16)
        with self.db:
            self.db.execute('INSERT INTO forms VALUES (?,1,0)',(key,))
            self.db.execute('INSERT INTO versions VALUES (?,1,?)',(key,json.dumps(schema)))
        return key

    def get(self,key):
        row=self.db.execute('SELECT f.*,v.schema FROM forms f JOIN versions v ON v.form_id=f.id AND v.revision=f.revision WHERE f.id=?',(key,)).fetchone()
        if row is None:raise FormError('Form not found.')
        return dict(id=row['id'],revision=row['revision'],open=bool(row['open']),schema=json.loads(row['schema']))

    def revise(self,key,revision,schema):
        if type(revision) is not int or revision<1:raise FormError('Invalid form revision.')
        schema=definition(schema)
        with self.db:
            cursor=self.db.execute('UPDATE forms SET revision=revision+1 WHERE id=? AND revision=?',(key,revision))
            if not cursor.rowcount:raise FormError('Form changed. Reload before editing.')
            self.db.execute('INSERT INTO versions VALUES (?,?,?)',(key,revision+1,json.dumps(schema)))
        return revision+1

    def set_open(self,key,opened):
        if type(opened) is not bool:raise FormError('Open state must be boolean.')
        with self.db:
            if not self.db.execute('UPDATE forms SET open=? WHERE id=?',(int(opened),key)).rowcount:
                raise FormError('Form not found.')

    def submit(self,key,revision,values,request_key):
        if type(revision) is not int or revision<1:raise FormError('Invalid form revision.')
        bounded(request_key,'Request key',100)
        # IMMEDIATE serializes submit, close and revise checks across connections.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            previous=self.db.execute('SELECT * FROM responses WHERE form_id=? AND request_key=?',(key,request_key)).fetchone()
            if previous:
                old=self.db.execute('SELECT schema FROM versions WHERE form_id=? AND revision=?',(key,previous['revision'])).fetchone()
                normalized=answers(json.loads(old['schema']),values)
                if previous['revision']!=revision or json.loads(previous['answers'])!=normalized:
                    raise FormError('Request key already used for a different response.')
                return previous['id']
            form=self.get(key)
            if not form['open']:raise FormError('This form is closed.')
            if form['revision']!=revision:raise FormError('Questions changed. Reload the form before submitting.')
            normalized=answers(form['schema'],values);response_id=secrets.token_urlsafe(16)
            self.db.execute('INSERT INTO responses VALUES (?,?,?,?,?,?)',(response_id,key,revision,datetime.now(timezone.utc).isoformat(),json.dumps(normalized),request_key))
        return response_id

    def inbox(self,key):
        self.get(key)
        rows=self.db.execute('SELECT r.*,v.schema FROM responses r JOIN versions v ON r.form_id=v.form_id AND r.revision=v.revision WHERE r.form_id=? ORDER BY r.rowid DESC',(key,))
        return [dict(id=r['id'],revision=r['revision'],submitted_at=r['submitted_at'],answers=json.loads(r['answers']),schema=json.loads(r['schema'])) for r in rows]

    def export_csv(self,key):
        # Long format retains original field labels and types across revisions.
        out=io.StringIO(newline='');writer=csv.writer(out)
        writer.writerow(['response_id','submitted_at_utc','revision','field_id','label','type','answer'])
        for response in self.inbox(key):
            for field in response['schema']['fields']:
                value=response['answers'][field['id']]
                if type(value) is bool:value='true' if value else 'false'
                writer.writerow([csv_cell(v) for v in [response['id'],response['submitted_at'],response['revision'],field['id'],field['label'],field['type'],value]])
        return out.getvalue()
