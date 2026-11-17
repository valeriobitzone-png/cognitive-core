"""Loopback-only JSON REST adapter for external agents.

No remote exposure or auth. Do not place behind a public reverse proxy.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlsplit,parse_qs
from .engine import CognitiveCore


def serve(core: CognitiveCore,port=8731):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def admitted(self):
            allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if self.headers.get('Origin') or self.headers.get('Host') not in allowed:
                self.write(403,{'error':'browser origins and foreign hosts are not admitted'})
                return False
            return True

        def write(self,status,data):
            blob=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(blob)))
            self.end_headers();self.wfile.write(blob)

        def do_GET(self):
            if not self.admitted():return
            path=urlsplit(self.path)
            args=parse_qs(path.query)
            try:
                if path.path=='/v1/status':
                    result=core.status()
                elif path.path=='/v1/memory/search':
                    result=core.memory_search(args.get('q',[''])[0],int(args.get('limit',[10])[0]))
                elif path.path=='/v1/topics':
                    result=core.vault.list_topics()
                elif path.path=='/health':
                    from . import __version__
                    result={'ok':True,'version':__version__}
                else:
                    self.write(404,{'error':'unknown endpoint'});return
                self.write(200,result)
            except Exception as exc:
                self.write(400,{'error':type(exc).__name__,'message':str(exc)[:200]})

        def do_POST(self):
            if not self.admitted():return
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    self.write(415,{'error':'application/json required'});return
                n=int(self.headers.get('Content-Length','0'))
                if not (0<n<=64_000):
                    self.write(413,{'error':'invalid request size'});return
                from worldcore.bridge import _decode_request
                payload=_decode_request(self.rfile.read(n))
                if self.path=='/v1/events':
                    result=core.observe(payload)
                elif self.path=='/v1/topics/resume':
                    result={'job_id':core.resume(payload['topic_id'],payload.get('seed_urls'))}
                elif self.path=='/v1/work/once':
                    result=core.work_once(dry_run=bool(payload.get('dry_run',False)))
                else:
                    self.write(404,{'error':'unknown endpoint'});return
                self.write(200,result)
            except Exception as exc:
                self.write(400,{'error':type(exc).__name__,'message':str(exc)[:200]})

        def log_message(self,format,*args):
            return

    server=HTTPServer(('127.0.0.1',port),Handler)
    print(f'LOCAL API http://127.0.0.1:{port} (not authenticated; do not expose remotely)',flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
