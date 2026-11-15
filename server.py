"""Loopback development API with distinct owner and respondent access."""
import argparse
from collections import deque
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from forms import Forms, FormError

MAX_BODY=160_000
ID=r'[A-Za-z0-9_-]{20,30}'


def make_server(path,owner_token,port=5143,submission_limit=60):
    if not isinstance(owner_token,str) or len(owner_token)<32 or not owner_token.isascii():
        raise ValueError('Set a random ASCII owner token with at least 32 characters.')
    Forms(path).close()
    recent=deque();gate=threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass # Never log credentials, answers or request URLs.

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def send(self,status,value,kind='application/json'):
            body=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.send_header('Referrer-Policy','no-referrer')
            self.end_headers();self.wfile.write(body)

        def trusted(self):
            host=f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host')==host and self.headers.get('Origin','http://'+host)=='http://'+host

        def owner(self):
            supplied=self.headers.get('Authorization','')
            return hmac.compare_digest(supplied.encode(),('Bearer '+owner_token).encode())

        def do_GET(self):self.dispatch(False)
        def do_POST(self):self.dispatch(True)

        def dispatch(self,mutation):
            if not self.trusted():return self.send(403,{'error':'Use the exact loopback origin.'})
            if not mutation:
                assets={'/messages.js':('messages.js','text/javascript'),'/i18n.js':('i18n.js','text/javascript'),'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
                if re.fullmatch('/f/'+ID,self.path):
                    assets[self.path]=('index.html','text/html; charset=utf-8')
                if self.path in assets:
                    name,kind=assets[self.path]
                    return self.send(200,(Path(__file__).parent/'web'/name).read_bytes(),kind)
            is_owner=self.path.startswith('/api/owner/')
            if is_owner and not self.owner():return self.send(401,{'error':'Owner authentication required.'})
            data={};store=None
            try:
                if mutation:
                    if self.headers.get('Content-Type')!='application/json' or self.headers.get('Transfer-Encoding'):
                        return self.send(415,{'error':'Send JSON with Content-Length.'})
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=MAX_BODY:return self.send(413,{'error':'Request must be at most 160000 bytes.'})
                    if not is_owner:
                        with gate:
                            now=time.monotonic()
                            while recent and recent[0]<now-60:recent.popleft()
                            if len(recent)>=submission_limit:return self.send(429,{'error':'Too many attempts. Retry in one minute.'})
                            recent.append(now)
                    raw=self.rfile.read(length)
                    if len(raw)!=length:raise FormError('Incomplete request.')
                    data=json.loads(raw)
                    if not isinstance(data,dict):raise FormError('Expected a JSON object.')
                store=Forms(path)
                if self.path=='/api/owner/forms':
                    if mutation:return self.send(201,store.get(store.create(data)))
                    ids=[row['id'] for row in store.db.execute('SELECT id FROM forms ORDER BY rowid DESC')]
                    return self.send(200,{'forms':[store.get(key) for key in ids]})
                match=re.fullmatch('/api/owner/forms/('+ID+')(?:/(open|revise|inbox|csv|delete-response))?',self.path)
                if match:
                    key,action=match.groups()
                    if action is None and not mutation:return self.send(200,store.get(key))
                    if action=='open' and mutation:
                        store.set_open(key,data['open']);return self.send(200,store.get(key))
                    if action=='revise' and mutation:
                        store.revise(key,data['revision'],data['schema']);return self.send(200,store.get(key))
                    if action=='inbox' and not mutation:return self.send(200,{'responses':store.inbox(key)})
                    if action=='csv' and not mutation:return self.send(200,store.export_csv(key).encode(),'text/csv; charset=utf-8')
                    if action=='delete-response' and mutation:
                        store.get(key)
                        with store.db:
                            removed=store.db.execute('DELETE FROM responses WHERE form_id=? AND id=?',(key,data['id'])).rowcount
                        if not removed:return self.send(404,{'error':'Response not found.'})
                        return self.send(200,{'deleted':True})
                match=re.fullmatch('/api/forms/('+ID+')(?:/(submit))?',self.path)
                if match:
                    key,action=match.groups()
                    if action is None and not mutation:
                        form=store.get(key)
                        if not form['open']:return self.send(410,{'error':'This form is closed.'})
                        return self.send(200,form)
                    if action=='submit' and mutation:
                        receipt=store.submit(key,data['revision'],data['answers'],data['request_key'])
                        return self.send(201,{'receipt':receipt})
                return self.send(404,{'error':'Not found.'})
            except FormError as e:return self.send(400,{'error':str(e)})
            except (KeyError,TypeError,ValueError,UnicodeError):return self.send(400,{'error':'Invalid request fields.'})
            except (sqlite3.Error,OSError):return self.send(503,{'error':'Storage or connection unavailable. Retry later.'})
            finally:
                if store is not None:store.close()

    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='form-meadow.sqlite3');parser.add_argument('--port',type=int,default=5143)
    args=parser.parse_args()
    server=make_server(args.db,os.environ.get('FORM_MEADOW_OWNER_TOKEN',''),args.port)
    print(f'Form Meadow development API: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
