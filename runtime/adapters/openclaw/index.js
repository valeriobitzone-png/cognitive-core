/** WorldCore OpenClaw native plugin.
 * Owns one persistent Python child per interpreter+database; fast JSONL IPC.
 * No raw prompts, tool args, model outputs or credentials are persisted.
 * Tested with a mock OpenClaw hook runner, not a production Gateway.
 */
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { createInterface } from 'node:readline';

const sessions = new Map();

function sessionKey(python, dbPath) { return JSON.stringify([python, dbPath]); }

function startSession(python, dbPath) {
  const env = { ...process.env };
  if (dbPath) env.WORLDCORE_DB = dbPath;
  const child = spawn(python, ['-u', '-m', 'worldcore.bridge', '--lines'], { env, stdio: ['pipe', 'pipe', 'ignore'] });
  const key = sessionKey(python, dbPath);
  const pending = new Map();
  const session = { child, pending };
  sessions.set(key, session);
  let finished = false;
  const failure = (error) => {
    if (finished) return;
    finished = true;
    if (sessions.get(key) === session) sessions.delete(key);
    for (const job of pending.values()) {
      clearTimeout(job.timer);
      job.reject(error);
    }
    pending.clear();
  };
  child.on('error', failure);
  child.on('exit', (code) => failure(new Error(`WorldCore bridge exited ${code}`)));
  child.stdin.on('error', failure);
  const lines = createInterface({ input: child.stdout });
  lines.on('line', (raw) => {
    try {
      if (Buffer.byteLength(raw, 'utf8') > 131072) throw new Error('bridge response too long');
      const result = JSON.parse(raw);
      const job = pending.get(result._req);
      if (!job) return;
      pending.delete(result._req);
      clearTimeout(job.timer);
      if (result.ok) job.resolve(result.result);
      else job.reject(new Error(result.error || 'bridge error'));
    } catch (error) { failure(error); child.kill(); }
  });
  process.once('exit', () => child.kill());
  return session;
}

export function shutdownBridge() {
  for (const session of sessions.values()) session.child.kill();
  sessions.clear();
}

export function bridge(payload, options = {}) {
  const python = options.python || process.env.WORLDCORE_PYTHON || 'python3';
  const dbPath = options.dbPath || process.env.WORLDCORE_DB || '';
  const key = sessionKey(python, dbPath);
  const session = sessions.get(key) || startSession(python, dbPath);
  return new Promise((resolve, reject) => {
    const id = randomUUID();
    const timer = setTimeout(() => {
      session.pending.delete(id);
      reject(new Error('WorldCore bridge timeout'));
      session.child.kill(); // Restart the child on the next request.
    }, 5000);
    session.pending.set(id, {resolve,reject,timer});
    const line = JSON.stringify({...payload, _req:id});
    if (Buffer.byteLength(line,'utf8')>64000) {
      clearTimeout(timer);
      session.pending.delete(id);
      reject(new Error('WorldCore request too large'));
      return;
    }
    session.child.stdin.write(line+'\n');
  });
}

export default {
  id: 'worldcore',
  name: 'WorldCore Cognitive Layer',
  register(api) {
    const config = api.pluginConfig || {};
    const options = {python:config.python, dbPath:config.dbPath};
    const owner = config.owner || process.env.WORLDCORE_OWNER || 'local';
    const space = config.space || process.env.WORLDCORE_SPACE || 'default';
    if (typeof api.registerTool === 'function') {
      api.registerTool({
        name:'worldcore_personal_advice',
        description:'Read authorized calendar/mail metadata and historical commute recommendations. No edits.',
        parameters:{type:'object', properties:{
          start_at:{type:'string'},end_at:{type:'string'},from_place:{type:'string'}},
          required:['start_at','end_at'], additionalProperties:false},
        async execute(_id, params) {
          const result=await bridge({op:'day_advice',owner,space,start_at:params.start_at,
              end_at:params.end_at,from_place:params.from_place},options);
          return {content:[{type:'text',text:JSON.stringify(result)}],details:{ok:true}};
        }
      });
    }
    if (typeof api.registerTool === 'function') {
      api.registerTool({
        name:'worldcore_whatif',
        description:'Compare counterfactual futures with evidence and unknowns; NO real execution.',
        parameters:{type:'object', properties:{
          question:{type:'string'},scenarios:{type:'array',items:{type:'object'}},
          objectives:{type:'array',items:{type:'object'}},
          failure_conditions:{type:'array',items:{type:'object'}}},
          required:['question','scenarios','objectives'],additionalProperties:false},
        async execute(_id,params) {
          const result=await bridge({op:'whatif_compare',owner,space,question:params.question,
            scenarios:params.scenarios,objectives:params.objectives,
            failure_conditions:params.failure_conditions || []},options);
          return {content:[{type:'text',text:JSON.stringify(result)}],details:{ok:true}};
        }
      });
    }
    if (typeof api.registerTool === 'function') {
      api.registerTool({
        name:'worldcore_whatif_backcast',
        description:'Find a read-only hypothetical path to numeric goals. Operator controls all real actions.',
        parameters:{type:'object', properties:{question:{type:'string'},target:{type:'object'},
          candidate_actions:{type:'array',items:{type:'object'}},max_depth:{type:'integer',minimum:1,maximum:5}},
          required:['question','target','candidate_actions'],additionalProperties:false},
        async execute(_id,params) {
          const result=await bridge({op:'whatif_backcast',owner,space,question:params.question,
            target:params.target,candidate_actions:params.candidate_actions,max_depth:params.max_depth||4},options);
          return {content:[{type:'text',text:JSON.stringify(result)}],details:{ok:true}};
        }
      });
    }
    api.on('gateway_stop', async () => { shutdownBridge(); });
    api.on('before_prompt_build', async (event) => {
      const question = typeof event.currentUserMessage === 'string' ? event.currentUserMessage : event.prompt;
      if (typeof question !== 'string' || !question.trim()) return;
      try {
        const result = await bridge({op:'context',owner,space,query:question.slice(0,1000)},options);
        if (result.context) return {prependContext:result.context};
      } catch { /* Fail open if recall unavailable; do not break model runs. */ }
    });
    api.on('after_tool_call', async (event) => {
      if (!event.toolName) return;
      try {
        await bridge({
          op:'event',owner,space,source:'openclaw',event_type:'tool_completed',
          summary:`tool=${String(event.toolName).slice(0,100)} status=${event.error ? 'error' : 'observed'}`,
          outcome:'observed',
        },options);
      } catch { /* Metadata-only telemetry is optional. */ }
    });
  },
};
