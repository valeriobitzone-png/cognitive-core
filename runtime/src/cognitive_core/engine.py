"""One end-to-end cycle: AWARE -> INTERPRET -> CURIOSITY -> WHAT IF
-> DECISION -> GOVERNOR -> WORKER -> VERIFY -> LEDGER.

The worker never assumes its findings are verified. No paid APIs or automatic
arbitrary external actions are implemented.
"""
import json
import time
from copy import deepcopy
from pathlib import Path
from .config import Settings
from .vault import Vault,ts
from .decision import DecisionPlane
from .research import Researcher,BudgetExceeded
from .world import WorldModel


class CognitiveCore:
    def __init__(self,settings: Settings=None):
        self.s=settings or Settings()
        self.decision=DecisionPlane(self.s)
        self.world=WorldModel()
        self._vault=None
        self._worldcore=None
        self._drive=None

    @property
    def drive(self):
        if self._drive is None:
            from .drive import CognitiveDrive
            self._drive=CognitiveDrive(self)
        return self._drive

    @property
    def worldcore(self):
        """One authoritative WHAT IF/calibration backend, opened only on demand."""
        if self._worldcore is None:
            from worldcore import WorldCore
            self._worldcore=WorldCore(self.s.worldcore_path)
        return self._worldcore

    def compare_futures(self,question,scenarios,*,objectives=None,failure_conditions=None,persist=True):
        return self.worldcore.compare_futures(self.s.owner,question,scenarios,space=self.s.namespace,
            objectives=[] if objectives is None else objectives,failure_conditions=failure_conditions,persist=persist)

    @property
    def vault(self):
        if self._vault is None:
            self._vault=Vault(self.s)
        return self._vault

    def close(self):
        self._drive=None
        if self._worldcore is not None:
            self._worldcore.close()
            self._worldcore=None
        if self._vault:
            self._vault.close()
            self._vault=None

    def observe(self,event: dict):
        """Significant structured event, e.g. {kind:'session_end', title, open_questions:[...]}.

        For greeting, return before touching the database, model or network.
        """
        if not isinstance(event,dict):
            raise TypeError('event must be a mapping')
        if len(json.dumps(event,allow_nan=False).encode('utf-8'))>64_000:
            raise ValueError('event too large')
        event=deepcopy(event)
        kind=str(event.get('kind','message'))
        if kind=='stimulus':
            return self.drive.ingest({k:v for k,v in event.items() if k!='kind'})
        first=self.decision.reflex.classify(event)
        if first.action=='WAIT':
            return {'action':'WAIT','cost':{'model_calls':0,'web_requests':0},'stored':False}
        d=self.decision.decide(event)
        if first.action=='REQUEST_APPROVAL':
            return {'decision':d.asdict(),'stored':False,'approved':False}
        eid=self.vault.event(kind,event)
        topic_ids=[]
        # Never invent unsupplied missing questions without a sufficiently capable extractor.
        if kind in ('session_end','question_open','research_requested'):
            questions=event.get('open_questions',[])
            if isinstance(questions,str):
                questions=[questions]
            if not isinstance(questions,list):
                questions=[]
            question=str(event.get('question','')).strip()
            if question:
                questions.insert(0,question)
            for q in questions[:12]:
                q=str(q).strip()
                if len(q)<10:
                    continue
                title=str(event.get('title','Research topic'))[:300]
                topic_id=self.vault.topic(title,q,importance=event.get('importance',.5),
                       status='paused' if event.get('paused',False) else 'open',
                       reason=str(event.get('reason','session-end gap')),trigger=kind)
                topic_ids.append(topic_id)
                if d.action=='PREPARE_SILENTLY' and self.vault.get_topic(topic_id)['status']=='open' and not event.get('paused',False):
                    # Search is never automatically enabled by creating a job.
                    self.vault.job(topic_id,plan={'question':q,'seed_urls':event.get('seed_urls',[])[:10],
                                                   'require_review':True})
        self.vault.audit('observe',{'event_id':eid,'decision':d.action,'topics':topic_ids})
        return {'decision':d.asdict(),'event_id':eid,'topics':topic_ids,
                'cost':{'model_calls':int(d.model_used),'web_requests':0},'stored':True}

    def resume(self,topic_id,seed_urls=None):
        t=self.vault.get_topic(topic_id)
        if not t:
            raise KeyError(topic_id)
        if t['status']=='discarded':
            raise PermissionError('discarded topics require explicit topic reactivation')
        if t['status']!='open':
            self.vault.set_topic_status(topic_id,'open')
        return self.vault.job(topic_id,plan={'question':t['question'],
                      'seed_urls':(seed_urls or [])[:10],'require_review':True})

    def _govern(self,job):
        if job['attempts'] > 3:
            return 'too many attempts'
        if not self.s.enable_web:
            return 'web is disabled in settings'
        if not self.s.domain_allowlist:
            return 'web allowlist is empty'
        if self.vault.usage('jobs_run') >= self.s.max_jobs_per_day:
            return 'daily job budget exhausted'
        if self.vault.usage('web_requests') >= self.s.max_web_requests_per_day:
            return 'daily request budget exhausted'
        return None

    def work_once(self, *, dry_run=False):
        """One bounded research job; resumable after interrupt.

        With no configured search endpoint or URLs, job becomes blocked.
        Local models cannot bypass limits, approvals, or web policy.
        """
        if dry_run:
            jobs=self.vault.pending_jobs()
            return {'dry_run':True,'pending':len(jobs),
                    'web_enabled':self.s.enable_web,'model_enabled':self.s.enable_local_model,
                    'paid_api_allowed':False}
        job=self.vault.lease_job()
        if not job:
            return {'status':'idle'}
        topic=self.vault.get_topic(job['topic_id'])
        if not topic or topic['status']!='open':
            self.vault.update_job(job['id'],lease_token=job['lease_token'],status='cancelled')
            return {'status':'cancelled'}
        plan=json.loads(job['plan'])
        checkpoint=json.loads(job['checkpoint'])
        completed=set(checkpoint.get('completed',[]))
        urls=checkpoint.get('source_urls') or plan.get('seed_urls',[])
        collected_all=bool(urls) and all(url in completed for url in urls[:self.s.max_web_requests_per_job])
        block=None if collected_all else self._govern(job)
        if block:
            self.vault.update_job(job['id'],lease_token=job['lease_token'],status='blocked',checkpoint={**checkpoint,'blocker':block})
            return {'status':'blocked','reason':block,'job_id':job['id']}
        failures=checkpoint.get('errors',[])
        sources=checkpoint.get('documents',[])
        imgs=checkpoint.get('images',[])
        requests_reserved=checkpoint.get('requests_reserved',0)
        def checkpoint_state():
            return {'completed':sorted(completed),'errors':failures,'documents':sources,
                    'images':imgs,'requests_reserved':requests_reserved,'source_urls':urls}
        def reserve_request():
            nonlocal requests_reserved
            if requests_reserved>=self.s.max_web_requests_per_job:
                raise BudgetExceeded('per-job HTTP request budget exhausted')
            if not self.vault.reserve_budget('web_requests',self.s.max_web_requests_per_day):
                raise BudgetExceeded('daily HTTP request budget exhausted')
            requests_reserved+=1
            self.vault.update_job(job['id'],lease_token=job['lease_token'],status='running',
                                  checkpoint=checkpoint_state())
        def blocked(reason):
            self.vault.update_job(job['id'],lease_token=job['lease_token'],status='blocked',
                                  checkpoint={**checkpoint_state(),'blocker':reason})
            return {'status':'blocked','reason':reason,'job_id':job['id']}
        researcher=Researcher(self.s,reserve_additional_request=reserve_request)
        # Search discovery requires configured SearXNG and counts against the same budget.
        if not urls and self.s.searxng_url:
            try:
                reserve_request()
                found=researcher.search(plan.get('question',topic['question']),
                                        limit=self.s.max_web_requests_per_job)
                urls=[x['url'] for x in found]
            except BudgetExceeded as exc:
                return blocked(str(exc))
            except Exception as exc:
                failures.append({'search':type(exc).__name__+': '+str(exc)[:200]})
        # No sources means no pretend research.
        if not urls:
            self.vault.update_job(job['id'],lease_token=job['lease_token'],status='blocked',checkpoint={**checkpoint_state(),'blocker':'no research source URLs; configure SearXNG or seed_urls'})
            return {'status':'blocked','reason':'no sources','errors':failures,'job_id':job['id']}
        if not collected_all and not self.vault.reserve_budget('jobs_run',self.s.max_jobs_per_day):
            self.vault.update_job(job['id'],lease_token=job['lease_token'],status='blocked',checkpoint={**checkpoint_state(),'blocker':'daily jobs quota'})
            return {'status':'blocked','reason':'daily jobs quota'}
        for url in urls[:self.s.max_web_requests_per_job]:
            if url in completed:
                continue
            try:
                reserve_request()  # robots.txt reservation; fetch reserves the page separately
                page=researcher.fetch(url)
                doc_id=self.vault.document(page['title'],page['text'],source_url=page['url'],
                                            kind='web_untrusted',metadata={'content_type':page['content_type']})
                self.vault.link(job['topic_id'],'researched_source',doc_id,'research_job:'+job['id'])
                if doc_id not in sources:
                    sources.append(doc_id)
                # Image URLs and alt are only DISCOVERED, never inspected or trusted as vision facts.
                for visual in page['images'][:10]:
                    item={'source_document':doc_id,'url':visual['url'],'alt_unverified':visual['alt']}
                    if item not in imgs:
                        imgs.append(item)
            except BudgetExceeded as exc:
                return blocked(str(exc))
            except Exception as exc:
                failures.append({'url':url,'error':type(exc).__name__+': '+str(exc)[:160]})
            completed.add(url)
            self.vault.update_job(job['id'],lease_token=job['lease_token'],status='running',checkpoint=checkpoint_state())
        # Durable checkpoint; content is source material, NOT automatically accepted factual claims.
        final_status='done' if sources else 'failed'
        with self.vault.transaction():
            self.vault.update_job(job['id'],lease_token=job['lease_token'],status=final_status,checkpoint={
                **checkpoint_state(),
                'verification':'pending_human_or_tool_review',
                'note':'Research evidence not asserted as verified truth'})
            self.vault.experience(job['topic_id'],'source_research',
                                  'collect inspectable candidate sources',
                                  f'{len(sources)} source documents; {len(failures)} failures',
                                  ','.join(sources))
        return {'status':final_status,'job_id':job['id'],'sources':sources,
                'images_discovered':len(imgs),'errors':failures,'verified_claims':0}

    def remember_claim(self,topic_id,statement,document_id,excerpt,stance='supports'):
        """Provenance: even with attached evidence, source-backed is NOT a tested truth."""
        cid=self.vault.claim(topic_id,statement)
        eid=self.vault.add_evidence(cid,document_id,excerpt,stance=stance)
        return {'claim_id':cid,'evidence_id':eid,'status':'source_backed' if stance=='supports' else 'unverified'}

    def memory_search(self,query,limit=10):
        limit=min(50,max(1,int(limit)))
        documents=self.vault.search(query,limit)
        memories=[]
        if self._worldcore is not None or self.s.worldcore_path.exists():
            memories=[{'id':m['id'],'title':m['fact_key'],'excerpt':m['value'][:500],
                       'source_url':'','kind':'worldcore_memory','source':m['source']}
                      for m in self.worldcore.recall(self.s.owner,query,space=self.s.namespace,limit=limit)]
        # Alternate stores so a full page of documents cannot hide the first memory.
        result=[]
        for i in range(max(len(documents),len(memories))):
            if i<len(documents):result.append(documents[i])
            if i<len(memories):result.append(memories[i])
        return result[:limit]

    def status(self):
        return {'namespace':self.s.namespace,'local_model_enabled':self.s.enable_local_model,
                'web_enabled':self.s.enable_web,'paid_api_calls_allowed':False,
                'topics':len(self.vault.list_topics()),
                'pending_jobs':len(self.vault.pending_jobs()),
                'web_requests_today':self.vault.usage('web_requests'),
                'jobs_today':self.vault.usage('jobs_run')}
