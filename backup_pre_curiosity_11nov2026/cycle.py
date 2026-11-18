"""Restartable local cognitive cycle; one atomic, bounded stage per tick.

The only autonomous action is recording an inspectable research note. WHAT IF
results retain simulation-only authority; no semantic truth or usefulness is learned.
"""
import json
import time

from .experimental import check_storage, encoded
from .drive import instant


def tick(core, topic_id):
    v = core.vault
    topic = v.get_topic(topic_id)
    if not topic:raise KeyError(topic_id)
    if topic['status'] != 'open':
        return {'status':'stopped','reason':'topic '+topic['status']}
    started = time.monotonic()
    # BEGIN IMMEDIATE serializes competing ticks and prevents duplicate actions.
    with v.transaction():
        row = v.db.execute('SELECT * FROM cognitive_cycles WHERE namespace=? AND topic_id=?',
                           (v.ns,topic_id)).fetchone()
        stage = row['stage'] if row else 'curiosity'
        state = json.loads(row['checkpoint']) if row else {}
        if stage in ('done','abstained','stopped'):
            return {'status':stage,'checkpoint':state}
        if not v.reserve_budget('cycle_ticks',core.s.max_cycle_ticks_per_day):
            return {'status':'blocked','reason':'daily cycle tick budget exhausted'}
        check_storage(core, 262_144)
        # Recheck under the write lock: pause/discard is authoritative.
        if v.get_topic(topic_id)['status'] != 'open':
            return {'status':'stopped','reason':'topic no longer open'}
        if stage == 'curiosity':
            # Feed context comes only from host-configured projects. No new projects
            # or permissions are inferred from imported text.
            result = core.drive.ingest({'source_kind':'manual','source_ref':'topic:'+topic_id,
                'occurred_at':instant(),'title':topic['title'][:300],
                'summary':topic['question'][:12000]})
            ident = result.get('opportunity_id')
            if not ident and result.get('stimulus_id'):
                old = v.db.execute('SELECT id FROM drive_opportunities WHERE namespace=? AND stimulus_id=?',
                                   (v.ns,result['stimulus_id'])).fetchone()
                ident = old['id'] if old else None
            state = {'opportunity_id':ident,'epistemic':'INFERRED','action':'record_local_note',
                     'authority':core.s.execution_mode,'model_calls':0,'web_requests':0}
            if ident:
                item = core.drive._get(ident)
                if item['status']=='dismissed' or (item['topic_id'] and item['topic_id']!=topic_id):
                    state['reason']='dismissed or already bound opportunity';stage='abstained'
                else:
                    v.db.execute('UPDATE drive_opportunities SET topic_id=? WHERE namespace=? AND id=?',
                                 (topic_id,v.ns,ident))
                    v.link(topic_id,'curiosity',ident,'open_topic_gap')
                    stage='research'
            else:
                state['reason']='no matching trusted project';stage='abstained'
        else:
            item = core.drive._get(state['opportunity_id'])
            if item['status']=='dismissed':
                return {'status':'stopped','reason':'opportunity dismissed'}
            if stage == 'research':
                hits = core.memory_search(topic['question'],limit=core.s.max_cycle_sources)
                # Exclude notes created by this cycle: self-citation cannot supply evidence.
                hits = [h for h in hits if h.get('kind')!='cognitive_note']
                state['sources'] = hits
                if hits:stage='whatif'
                else:
                    state['reason']='no local evidence; web requires explicit separate opt-in'
                    stage='abstained'
            elif stage == 'whatif':
                # Two honest alternatives. No made-up utility scores or automatic
                # claims of interval dominance. Persist in the same Vault transaction
                # as the checkpoint, avoiding an unsafe two-database commit.
                state['whatif'] = core.compare_futures(topic['question'][:1000],
                    [{'id':'record_local_note','actions':[]},{'id':'wait','actions':[]}],
                    objectives=[],persist=False)
                state['simulation_status']='SIMULATED';stage='decide'
            elif stage == 'decide':
                advice=None
                if core.s.enable_local_model and core.s.local_model_gguf:
                    advice=core.assess_local({'kind':'question_open','question':topic['question'][:600]},core.s.home,
                        timeout_seconds=max(.1,core.s.max_cycle_seconds-2))
                    state['local_advice']=advice
                    state['model_calls']+=advice['model_calls']
                if advice and advice['decision']['action'] in ('WAIT','ASK_FOR_CONTEXT'):
                    state['reason']='local advisor abstained; no action permitted';stage='abstained'
                state['decision'] = {'action':'record_local_note','external_action':False,
                    'reason':'bounded local evidence collection permitted; semantic judgment deferred',
                    'whatif_abstention':state['whatif']['confidence_gate']}
                if stage=='abstained':
                    state['decision']['action']='WAIT';state['decision']['reason']=state['reason']
                core.drive._decision(item['id'],'abstained' if stage=='abstained' else 'local_note_allowed',state['decision']['reason'],instant())
                if stage!='abstained':stage='act'
            elif stage == 'act':
                # Recheck bridge provenance after operator rollback/replacement.
                for hit in state['sources']:
                    if hit.get('batch_id'):
                        batch = v.db.execute('SELECT status FROM lab_batches WHERE namespace=? AND id=?',
                                             (v.ns,hit['batch_id'])).fetchone()
                        if not batch or batch['status']!='active':
                            state['reason']='source batch withdrawn';stage='abstained';break
                if stage=='act':
                    body = encoded({'question':topic['question'],'sources':state['sources'],
                                    'verification':'retrieval_only_not_truth','epistemic':'INFERRED'})
                    if len(body.encode())>core.s.max_text_bytes:
                        raise ValueError('cycle note exceeds text budget')
                    doc = v.document(topic['title'],body,'cycle:'+topic_id,'cognitive_note',
                                     {'epistemic':'INFERRED','verification':'retrieval_only_not_truth'})
                    v.link(topic_id,'local_research_note',doc,'bounded_cognitive_cycle')
                    state['document_id']=doc;stage='learn'
            elif stage == 'learn':
                document = v.get_document(state['document_id'])
                if not document:raise ValueError('cycle action lacks evidence')
                state['learning'] = {'epistemic':'OBSERVED','note_persisted':True,'retrieved_sources':len(state['sources']),
                    'truth_updates':0,'model_weight_updates':0,'usefulness':'unverified',
                    'observed_note_sha256':document['sha256']}
                v.experience(topic_id,'local_cognitive_cycle','persist inspectable candidate evidence',
                             encoded(state['learning']),document['id'])
                v.db.execute("UPDATE drive_opportunities SET status='researched' WHERE namespace=? AND id=?",
                             (v.ns,item['id']))
                core.drive._decision(item['id'],'researched','local note persisted; conclusions require verification',instant())
                stage='done'
            else:raise ValueError('unknown cognitive checkpoint stage')
        if time.monotonic()-started>core.s.max_cycle_seconds:
            # All Vault changes roll back together. No external effects to repeat.
            raise TimeoutError('cycle stage time budget exhausted')
        v.db.execute('''INSERT INTO cognitive_cycles VALUES(?,?,?,?) ON CONFLICT(namespace,topic_id)
            DO UPDATE SET stage=excluded.stage,checkpoint=excluded.checkpoint''',
            (v.ns,topic_id,stage,encoded(state)))
        v.audit('cognitive_tick',{'topic_id':topic_id,'stage':stage,'authority':core.s.execution_mode})
    return {'status':stage,'topic_id':topic_id,'checkpoint':state}
