import {performance} from 'node:perf_hooks';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {bridge,shutdownBridge} from '../adapters/openclaw/index.js';
const tmp=mkdtempSync(join(tmpdir(),'worldcore-bench-'));
const options={dbPath:join(tmp,'bench.db')};
try {
  const started=performance.now();
  await bridge({op:'remember',owner:'bench',key:'term',value:'one memory'},options);
  const cold=performance.now()-started;
  const times=[];
  for(let i=0;i<100;i++){
    const start=performance.now();
    const out=await bridge({op:'context',owner:'bench',query:'term'},options);
    if(!out.context.includes('one memory'))throw Error('memory mismatch');
    times.push(performance.now()-start);
  }
  const sorted=times.sort((a,b)=>a-b);
  console.log(JSON.stringify({coldStartMs:+cold.toFixed(2),warmP50Ms:+sorted[49].toFixed(2),warmP95Ms:+sorted[94].toFixed(2),requests:100,note:'single persistent local Python process; synthetic test'},null,2));
}finally{shutdownBridge();rmSync(tmp,{recursive:true,force:true});}
