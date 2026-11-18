import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import plugin, { bridge, shutdownBridge } from '../adapters/openclaw/index.js';

const dir = mkdtempSync(join(tmpdir(), 'worldcore-oc-'));
const dbPath = join(dir, 'test.sqlite');
const python = process.env.WORLDCORE_PYTHON || 'python3';
const options = { python, dbPath };
after(() => { shutdownBridge(); rmSync(dir,{recursive:true,force:true}); });

test('OpenClaw native hook registration and context recall', async () => {
  const hooks = {};
  plugin.register({pluginConfig: options, on: (event, callback) => {hooks[event] = callback;}});
  assert.deepEqual(Object.keys(hooks).sort(), ['after_tool_call','before_prompt_build','gateway_stop']);
  await bridge({op: 'remember', owner: 'local', key: 'project.focus', value: 'predictive cognition'}, options);
  const out = await hooks.before_prompt_build({currentUserMessage: 'project focus'});
  assert.match(out.prependContext, /predictive cognition/);
  assert.equal(await hooks.before_prompt_build({currentUserMessage: ''}), undefined);
});

test('OpenClaw observes metadata, never raw result', async () => {
  const hooks = {};
  plugin.register({pluginConfig: options, on: (event, callback) => {hooks[event] = callback;}});
  await hooks.after_tool_call({toolName:'exec', params:{password:'DO_NOT_PERSIST'}, result:'sk-PRIVATE-DO_NOT_PERSIST', error:null});
  const raw = await bridge({op:'event', owner:'local', source:'openclaw', event_type:'test', summary:'safe'}, options);
  assert.equal(raw.event.summary, 'safe');
  const pythonDump = spawnSync(python,['-c',"import json, sqlite3, sys; db=sqlite3.connect(sys.argv[1]); print(json.dumps([r[0] for r in db.execute('select summary from events')]))",dbPath],{encoding:'utf8'});
  assert.doesNotMatch(pythonDump.stdout,/DO_NOT_PERSIST|PRIVATE/);
  const { stdout } = spawnSync(python, ['-m', 'worldcore', '--db', dbPath, 'doctor'], {encoding:'utf8'});
  assert.equal(JSON.parse(stdout).integrity, 'ok');
});

test('OpenClaw bridge fail-open for missing interpreter', async () => {
  const hooks={};
  plugin.register({pluginConfig:{python:'does-not-exist-interpreter',dbPath},on:(e,cb)=>hooks[e]=cb});
  const r=await hooks.before_prompt_build({prompt:'test'});
  assert.equal(r,undefined);
});

test('OpenClaw concurrent requests are correlated and not interchanged', async () => {
  const results=await Promise.all(Array.from({length:24},(_,i)=>bridge({op:'remember',owner:'multi',key:`k${i}`,value:`unique ${i}`},options)));
  assert.equal(results.length,24);
  for(let i=0;i<24;i++) assert.equal(results[i].memory.fact_key,`k${i}`);
  const contexts=await Promise.all(Array.from({length:24},(_,i)=>bridge({op:'context',owner:'multi',query:`k${i}`},options)));
  contexts.forEach((x,i)=>assert.match(x.context,new RegExp(`k${i} \\(`)));
});

test('OpenClaw gateway_stop cleans persistent child and future startup works',async()=>{
  const hooks={};
  plugin.register({pluginConfig:options,on:(e,fn)=>hooks[e]=fn});
  await hooks.gateway_stop();
  const out=await bridge({op:'context',owner:'local',query:'project focus'},options);
  assert.match(out.context,/predictive cognition/);
});
