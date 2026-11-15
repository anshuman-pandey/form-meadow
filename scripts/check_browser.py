import os,secrets,subprocess,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import make_server
with tempfile.TemporaryDirectory() as folder:
 token=secrets.token_urlsafe(32);server=make_server(folder+'/db',token,0);thread=threading.Thread(target=server.serve_forever);thread.start()
 try:subprocess.run(['node','browser.test.cjs'],check=True,env={**os.environ,'BASE_URL':f'http://127.0.0.1:{server.server_port}','TEST_OWNER_TOKEN':token})
 finally:server.shutdown();server.server_close();thread.join()
