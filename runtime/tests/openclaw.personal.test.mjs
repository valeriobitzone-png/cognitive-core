import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import plugin,{shutdownBridge} from '../adapters/openclaw/index.js';

test('OpenClaw exposes read-only WorldCore personal advice',async()=>{
  const d=fs.mkdtempSync(path.join(os.tmpdir(),'wc-personal-'));
  const schema=[];const hooks={};
  const api={pluginConfig:{dbPath:path.join(d,'db.sqlite'),python:process.env.WORLDCORE_PYTHON||'python3'},
      on:(name,fn)=>hooks[name]=fn,registerTool:(tool)=>schema.push(tool)};
  try {
    plugin.register(api);
    assert.deepEqual(schema.map(x=>x.name).sort(),['worldcore_personal_advice','worldcore_whatif','worldcore_whatif_backcast'].sort());
    const response=await schema.find(x=>x.name==='worldcore_personal_advice').execute('req1',{start_at:'2031-01-01T08:00:00Z',end_at:'2031-01-01T18:00:00Z'});
    assert.equal(JSON.parse(response.content[0].text).events.length,0);
    const future=await schema.find(x=>x.name==='worldcore_whatif').execute('req2',{
      question:'Two choices',scenarios:[{id:'A',actions:[]},{id:'B',actions:[]}],objectives:[]
    });
    const result=JSON.parse(future.content[0].text);
    assert.equal(result.action_executed,false);
  } finally {
    shutdownBridge();fs.rmSync(d,{recursive:true,force:true});
  }
});
