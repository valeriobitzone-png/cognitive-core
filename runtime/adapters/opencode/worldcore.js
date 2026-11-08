/* OpenCode V1 plugin: metadata-only observations over persistent local JSONL.
 * No raw prompts, tool args or output are stored. What-if tools are in MCP.
 * Supports the documented V1 `tool.execute.after` API (not OpenCode V2).
 */
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { randomUUID } from 'node:crypto';
const sessions=new Map();
const valid=name=>typeof name==='string'&&/^[A-Za-z][A-Za-z0-9_./:-]{0,100}$/.test(name);
const key=()=>JSON.stringify([process.env.WORLDCORE_PYTHON||'python3',process.env.WORLDCORE_DB||'',process.env.WORLDCORE_OWNER||'local',process.env.WORLDCORE_SPACE||'default']);
function launch(identifier){
  const child=spawn(process.env.WORLDCORE_PYTHON||'python3',['-u','-m','worldcore.bridge','--lines'],
    {env:{...process.env},stdio:['pipe','pipe','ignore']});
  const pending=new Map();
  const session={child,pending};sessions.set(identifier,session);
  let closed=false;
  function fail(e){
    if(closed)return;closed=true;
    if(sessions.get(identifier)===session)sessions.delete(identifier);
    for(const job of pending.values()){clearTimeout(job.timer);job.reject(e)}
    pending.clear();
  }
  child.on('error',fail);
  child.on('exit',code=>fail(new Error(`WorldCore bridge exited ${code}`)));
  child.stdin.on('error',fail);
  createInterface({input:child.stdout}).on('line',raw=>{
    try{
      if(Buffer.byteLength(raw,'utf8')>131072)throw new Error('response too large');
      const result=JSON.parse(raw),job=pending.get(result._req);
      if(!job)return;
      pending.delete(result._req);clearTimeout(job.timer);
      if(result.ok)job.resolve(result.result);else job.reject(new Error(result.error||'WorldCore bridge error'));
    }catch(err){fail(err);child.kill()}
  });
  return session;
}
export function shutdownOpenCodeBridge(){
  for(const session of sessions.values())session.child.kill();
  sessions.clear();
}
process.once('exit',shutdownOpenCodeBridge);
async function request(payload){
  const identifier=key();
  const session=sessions.get(identifier)||launch(identifier);
  return new Promise((resolve,reject)=>{
    const id=randomUUID(),line=JSON.stringify({...payload,_req:id});
    if(Buffer.byteLength(line,'utf8')>64000){reject(new Error('oversized request'));return}
    const timer=setTimeout(()=>{session.pending.delete(id);session.child.kill();reject(new Error('WorldCore timeout'))},4000);
    session.pending.set(id,{resolve,reject,timer});
    try{session.child.stdin.write(line+'\n')}catch(e){session.pending.delete(id);clearTimeout(timer);reject(e)}
  });
}
export async function observeWorldCoreTool(name,completed,source='opencode'){
  if(!valid(name))return false;
  try{
    await request({op:'event',owner:process.env.WORLDCORE_OWNER||'local',
      space:process.env.WORLDCORE_SPACE||'default',source,
      event_type:'tool_event',outcome:'observed',summary:`tool=${name} completed=${!!completed}`});
    return true;
  }catch{return false}
}
export const WorldCorePlugin=async _ctx=>({
  'tool.execute.after':async(input,output)=>{
    await observeWorldCoreTool(input?.tool,!output?.error);
  },
});
