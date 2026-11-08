import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { WorldCorePlugin, shutdownOpenCodeBridge } from '../adapters/opencode/worldcore.js';
import { WorldCoreV2Plugin } from '../adapters/opencode/worldcore-v2.js';
import v2Definition from '../adapters/opencode/v2/index.js';

const dir=mkdtempSync(join(tmpdir(),'wc-opencode-'));
const python=process.env.WORLDCORE_PYTHON||'python3';
const db=join(dir,'opencode.db');
const old={db:process.env.WORLDCORE_DB,owner:process.env.WORLDCORE_OWNER,space:process.env.WORLDCORE_SPACE,python:process.env.WORLDCORE_PYTHON};
process.env.WORLDCORE_DB=db;process.env.WORLDCORE_OWNER='tenant_opencode';process.env.WORLDCORE_SPACE='project_a';
after(()=>{
 for(const [key,value] of Object.entries({WORLDCORE_DB:old.db,WORLDCORE_OWNER:old.owner,WORLDCORE_SPACE:old.space,WORLDCORE_PYTHON:old.python})) {
   if(value===undefined)delete process.env[key];else process.env[key]=value;
 }
 shutdownOpenCodeBridge();
 rmSync(dir,{recursive:true,force:true});
});
function observations(){
 const run=spawnSync(python,['-c',`import json,sqlite3,sys
c=sqlite3.connect(sys.argv[1]);print(json.dumps(c.execute("SELECT owner,space,summary FROM events ORDER BY at").fetchall()))`,db],{encoding:'utf8'});
 assert.equal(run.status,0,run.stderr);
 return JSON.parse(run.stdout);
}
test('OpenCode V1 observes real bridge transaction, no secret args',async()=>{
 const hooks=await WorldCorePlugin({});
 assert.equal(typeof hooks['tool.execute.after'],'function');
 await hooks['tool.execute.after']({tool:'bash',args:{command:'sk-CREDENTIAL_SECRET'}},{error:null,result:'DONT_STORE_THIS'});
 const records=observations();
 assert.equal(records.length,1);
 assert.deepEqual(records[0],['tenant_opencode','project_a','tool=bash completed=true']);
 assert.doesNotMatch(JSON.stringify(records),/CREDENTIAL_SECRET|DONT_STORE_THIS/);
});
test('OpenCode V2 registers event hook and records failure safely',async()=>{
 const registry={};
 await WorldCoreV2Plugin({tool:{hook:async(name,fn)=>{registry[name]=fn}}});
 assert.deepEqual(Object.keys(registry),['execute.after']);
 await registry['execute.after']({tool:'web.read',status:'error',error:{message:'PRIVATE_SECRET'}});
 const records=observations();
 assert.equal(records.length,2);
 assert.deepEqual(records[1],['tenant_opencode','project_a','tool=web.read completed=false']);
 assert.doesNotMatch(JSON.stringify(records),/PRIVATE_SECRET/);
});
test('Invalid tool names are rejected before subprocess execution',async()=>{
 const hooks=await WorldCorePlugin({});
 await hooks['tool.execute.after']({tool:'bash; rm -rf /'},{});
 assert.equal(observations().length,2);
});
test('Failed interpreter does not block V2 host',async()=>{
 process.env.WORLDCORE_PYTHON='worldcore_nonexistent_python_abc';
 let handler;
 await WorldCoreV2Plugin({tool:{hook:async(_,fn)=>{handler=fn}}});
 await handler({tool:'read',status:'completed'});
 assert.equal(observations().length,2);
 process.env.WORLDCORE_PYTHON=old.python||python;
});

test('V2 default entry is a loadable definition with lifecycle cleanup',async()=>{
 const hooks={};
 assert.equal(v2Definition.id,'worldcore');
 const dispose=await v2Definition.setup({tool:{hook:async(name,fn)=>{hooks[name]=fn}}});
 assert.equal(typeof hooks['execute.after'],'function');
 assert.equal(typeof dispose,'function');
});

test('V2 Code Mode error metadata is not reported as successful telemetry',async()=>{
 let handler;
 await WorldCoreV2Plugin({tool:{hook:async(_,fn)=>{handler=fn}}});
 await handler({tool:'execute',status:'completed',result:{metadata:{error:true},content:[{text:'DO_NOT_STORE_ERROR_CONTENT'}]}});
 const records=observations();
 assert.equal(records.at(-1)[2],'tool=execute completed=false');
 assert.doesNotMatch(JSON.stringify(records),/DO_NOT_STORE_ERROR_CONTENT/);
});
