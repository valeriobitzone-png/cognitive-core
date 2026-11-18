"""One bounded application over the existing Core, not a second agent/database."""
import json,math,re,sqlite3,time
from .decision import TRIVIAL
from .models import ModelGateway
from .skills import SkillBook
from .experimental import check_storage,require_interactive
from .vault import uid

OPS={
 'status':(), 'worldcore':('request',), 'turn':('text','ticks','use_model','model','use_memory'), 'tick':('topic_id',),
 'observe':('event',), 'search':('query','limit'), 'remember':('scope','key','value','source'),
 'project':('id','title','keywords'), 'whatif':('question','scenarios','objectives'),
 'import':('root','source'), 'rollback_import':('batch_id',), 'dream':(),
 'session_open':('domain','source','context_id','ttl_seconds'), 'session_close':('session_id',),
 'context':('context_id',), 'assist':('session_id','observation'),
 'model':('prompt','model','use_memory'), 'stop':(), 'start':(),
 'skill_propose':('name','input_type','output_type','development','evaluation'),
 'skill_adopt':('skill_id',), 'skill_use':('skill_id','value'),
 'feedback':('target_id','helpful','evidence_ref'),
}
INTERACTIVE={'remember','project','import','rollback_import','session_open','start','skill_propose','skill_adopt','feedback'}
READ_ONLY={'status','context','search','session_close','stop'}
SECRET=re.compile(r'(?i)(password|secret|token|credential|cookie|authorization|api_key)')
SENSITIVE=re.compile(r'(?i)(health|diagnos|mood|emotion|medical|location_exact|financial_balance|religion|politic|biometric)')

def label(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',value):raise ValueError('invalid bounded identifier')
    return value

class UnifiedProgram:
    def __init__(self,core):
        self.core=core;self.scope=(core.s.owner,core.s.namespace);self.sessions={};self._stop_requested=False
        self.models=ModelGateway(core,self);self.skills=SkillBook(self)

    def check_scope(self):
        if self.scope!=(self.core.s.owner,self.core.s.namespace):raise PermissionError('scope changed; construct a new Core')

    def stopped(self):
        if self._stop_requested:return True
        if self.core._vault is None and not self.core.s.db_path.exists():return False
        v=self.core.vault
        row=v.db.execute("SELECT payload FROM events WHERE namespace=? AND kind='program_control' ORDER BY rowid DESC LIMIT 1",(v.ns,)).fetchone()
        return bool(row and json.loads(row[0])['stopped'])

    def control(self,stopped):
        self.check_scope()
        if not stopped:require_interactive(self.core)
        if stopped:
            self._stop_requested=True;self.sessions.clear();self.skills.adopted.clear()
        try:
            with self.core.vault.transaction():
                check_storage(self.core,16384)
                self.core.vault.event('program_control',{'stopped':stopped})
        except (ValueError,OSError,sqlite3.Error):
            if not stopped:raise
            return {'status':'stopped','persisted':False,'external_actions':0}
        self._stop_requested=stopped
        return {'status':'stopped' if stopped else 'ready','persisted':True,'external_actions':0}

    def status(self):
        return {'program':'cognitive-core','protocol':'cognitive-program-v1','stopped':self.stopped(),
            'scope':{'owner':self.scope[0],'namespace':self.scope[1]},'operations':sorted(OPS),
            'components':{'memory':'canonical_vault_and_worldcore','boredom':'curiosity_and_opportunity_pool',
                'whatif':'worldcore','research':'existing_bounded_researcher','context':'world_user_cognitive',
                'attention':'session_ttl_scope_and_core_governor','skills':'bounded_data_recipes',
                'models':self.models.status(),'sensors':'host_push_only_no_capture','external_actions':'not_executed'},
            'paid_api_calls_allowed':False,'sessions_persisted':False,'model_resident_managed_by_core':False}

    def open_session(self,domain,source,context_id,ttl_seconds=300):
        self.check_scope();require_interactive(self.core)
        if domain not in ('game','desktop','phone','real_world'):raise ValueError('unknown observation domain')
        label(source);label(context_id)
        if type(ttl_seconds) is not int or not 1<=ttl_seconds<=3600:raise ValueError('session TTL must be 1..3600 seconds')
        now=time.time();self.sessions={k:v for k,v in self.sessions.items() if v['expires_at']>now}
        if len(self.sessions)>=16:raise ValueError('session budget exhausted')
        ident=uid('session');self.sessions[ident]={'domain':domain,'source':source,'context_id':context_id,'expires_at':now+ttl_seconds}
        return {'session_id':ident,**self.sessions[ident],'scope':'observe_and_advise_only','external_actions':False}

    def _session(self,ident):
        session=self.sessions.get(ident)
        if not session or time.time()>=session['expires_at']:raise PermissionError('session absent, expired or revoked')
        return session

    def context(self,context_id,session=None):
        self.check_scope()
        if session is None:require_interactive(self.core)
        label(context_id);v=self.core.vault;out={}
        for layer in ('world','user','cognitive'):
            kind='program_context:'+context_id+':'+layer
            row=v.db.execute('SELECT payload FROM events WHERE namespace=? AND kind=? ORDER BY rowid DESC LIMIT 1',(v.ns,kind)).fetchone()
            value=json.loads(row[0]) if row else None
            if value and session and any(value[k]!=session[k] for k in ('domain','source')):value=None
            out[layer]=value if value and value['observed_at']<=time.time()<value['expires_at'] else {'status':'unknown_or_expired'}
        return {'context_id':context_id,'states':out,'verified_facts':0}

    def assist(self,session_id,observation):
        self.check_scope()
        if self.stopped():return {'status':'stopped','external_actions':0}
        session=self._session(session_id);o=observation;now=time.time()
        fields={'layer','domain','source','context_id','observed_at','ttl_seconds','epistemic','confidence','signals','sensitivity'}
        if not isinstance(o,dict) or set(o)!=fields:raise ValueError('invalid observation contract')
        if any(o[k]!=session[k] for k in ('domain','source','context_id')):raise PermissionError('observation outside session scope')
        layer=o['layer']
        if layer not in ('world','user','cognitive'):raise ValueError('unknown state layer')
        if layer=='user':require_interactive(self.core)
        if type(o['observed_at']) not in (int,float) or not math.isfinite(o['observed_at']) or not 0<=o['observed_at']<=now:raise ValueError('invalid observation time')
        if type(o['ttl_seconds']) is not int or not 1<=o['ttl_seconds']<=86400:raise ValueError('invalid observation TTL')
        if now>=o['observed_at']+o['ttl_seconds']:return {'status':'suppressed','reason':'stale','external_actions':0}
        if o['epistemic'] not in ('OBSERVED','SIMULATED','INFERRED'):raise ValueError('invalid evidence origin')
        if type(o['confidence']) not in (int,float) or not math.isfinite(o['confidence']) or not 0<=o['confidence']<=1:raise ValueError('invalid confidence')
        if o['sensitivity'] not in ('public','personal'):raise PermissionError('private observations are not stored')
        signals=o['signals']
        if not isinstance(signals,dict) or not 1<=len(signals)<=16:raise ValueError('bounded signals required')
        for key,value in signals.items():
            label(key)
            if SECRET.search(key) or (layer=='user' and SENSITIVE.search(key)):raise PermissionError('sensitive signal rejected')
            if type(value) not in (str,int,float,bool,type(None)):raise ValueError('signals must be scalar')
            if isinstance(value,str) and (len(value)>500 or re.search(r'(?i)(Bearer\s+\S+|sk-[A-Za-z0-9]{16,})',value)):raise ValueError('oversized or secret-like signal')
            if type(value) is float and not math.isfinite(value):raise ValueError('invalid signal number')
        raw=json.dumps(o,allow_nan=False)
        if len(raw.encode())>8000:raise ValueError('observation exceeds byte budget')
        record={**o,'expires_at':min(o['observed_at']+o['ttl_seconds'],session['expires_at']),'verified':False}
        v=self.core.vault
        with v.transaction():
            check_storage(self.core,32768)
            if not v.reserve_budget('program_observations',1000):raise ValueError('daily observation budget exhausted')
            v.event('program_context:'+o['context_id']+':'+layer,record)
        state=self.context(o['context_id'],session=session)
        question=signals.get('question')
        if isinstance(question,str) and len(question.strip())>=10:
            user=state['states']['user'].get('signals',{})
            cognitive=state['states']['cognitive'].get('signals',{})
            if user.get('quiet') is True or user.get('allow_advice') is False:
                return {'status':'silent','reason':'explicit user attention policy','context':state,'external_actions':0}
            if cognitive.get('available') is False:
                return {'status':'deferred','reason':'declared cognitive capacity unavailable','context':state,'external_actions':0}
            if o['epistemic']=='INFERRED' or o['confidence']<.7 or signals.get('conflict') is True:
                return {'status':'abstained','reason':'observation insufficient for proactive advice','context':state,'external_actions':0}
            if now-session.get('last_advice',float('-inf'))<15:
                return {'status':'silent','reason':'session advice cooldown','context':state,'external_actions':0}
            session['last_advice']=now
            return {'status':'suggestion','context':state,
                'cognitive':self.turn(question,ticks=8),'external_actions':0}
        return {'status':'recorded','context':state,'external_actions':0}

    def turn(self,text,ticks=8,use_model=False,model='local',use_memory=False):
        if not isinstance(text,str) or not 1<=len(text.encode())<=6000:raise ValueError('text must be 1..6000 bytes')
        if type(ticks) is not int or not 0<=ticks<=12:raise ValueError('turn ticks must be 0..12')
        if type(use_model) is not bool or type(use_memory) is not bool:raise ValueError('model choices must be boolean')
        self.check_scope()
        if TRIVIAL.fullmatch(text) or text.strip() in ('?', '.', '!', '…'):return {'status':'idle','text':'','model_calls':0,'web_requests':0,'stored':False}
        if self.stopped():return {'status':'stopped','external_actions':0}
        result=self.core.observe({'kind':'question_open','title':text[:200],'question':text},use_model=False)
        topic=result['topics'][0] if result.get('topics') else None;stages=[];began=time.monotonic()
        for _ in range(ticks):
            if not topic or self.stopped() or time.monotonic()-began>=self.core.s.max_cycle_seconds:break
            step=self.core.cycle_once(topic,allow_model=False);stages.append(step)
            if step['status'] in ('idle','blocked','done','abstained','stopped'):break
        sources=self.core.memory_search(text,limit=self.core.s.max_cycle_sources)
        answer=self.models.generate(text,model=model,use_memory=use_memory) if use_model else None
        status='completed' if stages and stages[-1]['status']=='done' else 'evidence_only' if sources else 'abstained'
        if stages and stages[-1]['status']=='blocked':status='blocked'
        elif stages and stages[-1]['status'] not in ('done','abstained','stopped'):status='pending'
        if answer and answer['status']=='generated':status='answered'
        if self.stopped():status='stopped'
        return {'status':status,'topic_id':topic,'cycle':stages,'sources':sources,
                'answer':answer,'model_calls':answer['model_calls'] if answer else 0,'external_actions':0,'web_requests':0,
                'answer_verified':False,'learning':'checkpoint_and_measured_outcomes_only'}

    def run(self,request):
        self.check_scope()
        if not isinstance(request,dict) or len(json.dumps(request,allow_nan=False).encode())>64000:raise ValueError('bounded request mapping required')
        op=request.get('op')
        if not isinstance(op,str) or op not in OPS:raise ValueError('unknown program operation')
        if set(request)-{'op',*OPS[op]}:raise ValueError('unexpected program request fields')
        if op in INTERACTIVE:require_interactive(self.core)
        if op=='status':return self.status()
        if op=='stop':return self.control(True)
        if op=='start':return self.control(False)
        if op=='turn' and isinstance(request.get('text'),str) and TRIVIAL.fullmatch(request['text']):return self.turn(**{k:v for k,v in request.items() if k!='op'})
        if self.stopped() and op not in READ_ONLY:return {'status':'stopped','external_actions':0}
        args={k:v for k,v in request.items() if k!='op'}
        if op=='worldcore':
            inner=args['request']
            if not isinstance(inner,dict) or not isinstance(inner.get('op'),str) or inner['op'].startswith('cognitive_'):
                raise ValueError('a nonrecursive WorldCore operation is required')
            from .worker import dispatch
            return dispatch(inner,self.core)
        if op=='turn':return self.turn(**args)
        if op=='model':return self.models.generate(**args)
        if op=='tick':return self.core.cycle_once(args.get('topic_id'),allow_model=False)
        if op=='observe':return self.core.observe(args['event'],use_model=False)
        if op=='search':return {'sources':self.core.memory_search(args['query'],args.get('limit',10))}
        if op=='remember':return {'id':self.core.memory.remember(**args)}
        if op=='project':return self.core.drive.upsert_project(args['id'],args['title'],args['keywords'])
        if op=='whatif':return self.core.compare_futures(args['question'],args['scenarios'],objectives=args.get('objectives',[]),persist=False)
        if op=='import':return self.core.import_lab(args['root'],source=args.get('source','package'))
        if op=='rollback_import':return self.core.rollback_lab(args['batch_id'])
        if op=='dream':return self.core.dream.run(idle=True)
        if op=='session_open':return self.open_session(**args)
        if op=='session_close':return {'revoked':self.sessions.pop(args['session_id'],None) is not None}
        if op=='context':
            require_interactive(self.core)
            return self.context(**args)
        if op=='assist':return self.assist(**args)
        if op=='skill_propose':return self.skills.propose(**args)
        if op=='skill_adopt':return self.skills.adopt(args['skill_id'])
        if op=='skill_use':return self.skills.use(args['skill_id'],args['value'])
        if op=='feedback':
            label(args['target_id'])
            if type(args['helpful']) is not bool or not isinstance(args['evidence_ref'],str) or not 1<=len(args['evidence_ref'])<=300:raise ValueError('bounded explicit feedback required')
            with self.core.vault.transaction():
                check_storage(self.core,16384);self.core.vault.event('program_feedback',args)
            return {'status':'recorded','truth_promoted':False}
        raise ValueError('operation not implemented')
