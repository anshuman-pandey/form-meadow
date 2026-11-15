"""Run a disposable create → submit → inbox → CSV workflow with synthetic data."""
import tempfile
from forms import Forms

with tempfile.TemporaryDirectory() as directory:
    store=Forms(directory+'/demo.sqlite3')
    try:
        form=store.create({'title':'Workshop signup','fields':[
            {'id':'name','label':'Your name','type':'text','required':True},
            {'id':'permission','label':'Contact me about this workshop','type':'consent','required':True}]})
        store.set_open(form,True)
        store.submit(form,1,{'name':'Ada (synthetic)','permission':True},'demo-request')
        print(store.export_csv(form),end='')
    finally:store.close()
