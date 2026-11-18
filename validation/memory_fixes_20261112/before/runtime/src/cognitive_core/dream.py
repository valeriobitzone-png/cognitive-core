"""Idle-gated, budgeted reflection. Produces hypotheses, never conclusions.

A dream reads existing memory claims, proposes at most MAX_HYPOTHESES, and stores them as
'hypothesis' rows that cannot be recalled as facts. A hypothesis is promoted only by an
independent verification supplied by the caller (source different from the dream itself),
so reflection never confirms itself.
"""
from .memory import Memory
MAX_HYPOTHESES=3
BUDGET='dream_cycles'


class Dreamer:
    def __init__(self,core):
        self.core=core;self.m=Memory(core);self.v=core.vault

    def run(self,idle=False,daily_limit=2,scope='dream'):
        if not idle:return {'status':'skipped','reason':'not idle'}
        if not self.v.reserve_budget(BUDGET,daily_limit):return {'status':'skipped','reason':'budget exhausted'}
        facts=self.v.db.execute("SELECT scope,key,value FROM mem_facts WHERE namespace=? AND retracted IS NULL AND valid_to IS NULL AND scope!=? AND key NOT LIKE 'hypothesis:%' ORDER BY recorded DESC LIMIT 50",(self.v.ns,scope)).fetchall()
        seen={};out=[]
        for f in facts:seen.setdefault(f['scope'],[]).append(f['key'])
        for s,keys in seen.items():
            if len(keys)>=2 and len(out)<MAX_HYPOTHESES:
                text='possible link between %s and %s in %s'%(keys[0],keys[1],s)
                i=self.m.remember(scope,'hypothesis:'+s+':'+keys[0]+'+'+keys[1],{'text':text,'status':'unverified'},'dream:self',agent='dream',kind='fact')
                out.append(i)
        self.v.audit('dream_cycle',{'hypotheses':len(out)})
        return {'status':'done','hypotheses':out}

    def promote(self,scope,key,verifier_source):
        h=self.m.recall(scope,key)
        if h is None:raise KeyError(key)
        if not verifier_source or verifier_source.startswith('dream:'):
            raise ValueError('a dream cannot verify itself')
        v=dict(h['value']);v['status']='verified'
        return self.m.remember(scope,key,v,verifier_source,agent='verifier')

    def grounding_check(self,scope,key):
        """A hypothesis must name keys that exist as live claims; ungrounded ones are rejected."""
        h=self.m.recall(scope,key)
        if h is None:return False
        parts=key.split(':',2)[-1].split('+')
        live={r['key'] for r in self.v.db.execute('SELECT key FROM mem_facts WHERE namespace=? AND retracted IS NULL AND valid_to IS NULL',(self.v.ns,))}
        return all(p in live for p in parts)

    def wake_context(self,limit=3,scope='dream'):
        """Short text handed to the next session: unverified hypotheses, clearly labelled as such."""
        rows=[r for r in self.m.search('possible link',limit=limit*3) if r['scope']==scope and r['value'].get('status')=='unverified'][:limit]
        return '\n'.join('[UNVERIFIED] '+r['value']['text'] for r in rows)
