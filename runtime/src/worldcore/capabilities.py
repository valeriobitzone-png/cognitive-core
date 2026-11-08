"""Host-neutral multimodal, conversation and capability evidence contracts.

Does NOT claim to recognize pixels or navigate websites by itself. Sensor/LLM
outputs are untrusted until an authorized adapter supplies grounded evidence.
"""
from __future__ import annotations
from .worldmodel import _valid_atom
import json

_MODALITIES={'text','image','video','audio','web','map','3d','code','sensor'}

class CapabilitiesMixin:
    def _init_capability_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS capability_observations(
         owner TEXT,space TEXT,id TEXT,modality TEXT,source TEXT,adapter TEXT,at TEXT,
         claims_json TEXT,confidence REAL,verification TEXT,PRIMARY KEY(owner,space,id));
        CREATE INDEX IF NOT EXISTS capability_by_modality ON capability_observations(owner,space,modality,at);
        CREATE TABLE IF NOT EXISTS skill_feedback(
         owner TEXT,space TEXT,id TEXT,skill TEXT,at TEXT,successful INTEGER,reason TEXT,
         PRIMARY KEY(owner,space,id));
        ''')

    def ingest_perception(self,owner,record,*,space='default'):
        """Grounded outputs of external host vision/ASR/browser etc; no raw media storage.

        The adapter must label verification, otherwise claims remain unverified.
        Do not pass a URL or text as commands to a browser/model automatically.
        """
        from .engine import WorldCoreError, _when, _json
        owner,space=_valid_atom(owner,'owner'),_valid_atom(space,'space')
        if not isinstance(record,dict):raise WorldCoreError('expected observation dictionary')
        needed={'id','modality','source','adapter','at','claims','confidence','verification'}
        if set(record)!=needed:raise WorldCoreError('observation schema mismatch')
        id,source,adapter=[_valid_atom(record[n],n) for n in ('id','source','adapter')]
        if record['modality'] not in _MODALITIES:raise WorldCoreError('unsupported modality')
        if record['verification'] not in ('unverified','user_verified','tool_verified','independent_source'):
            raise WorldCoreError('verification must be explicit')
        if type(record['confidence']) not in (float,int) or not 0<=record['confidence']<=1:
            raise WorldCoreError('confidence must be within 0..1')
        claims=record['claims']
        if not isinstance(claims,list) or not 1<=len(claims)<=30 or any(not isinstance(x,str) or not x.strip() or len(x)>400 for x in claims):
            raise WorldCoreError('claims must be 1..30 short statements')
        at=_when(record['at']);claims_raw=_json(claims)
        payload=(record['modality'],source,adapter,at,claims_raw,float(record['confidence']),record['verification'])
        with self._transaction():
            old=self.db.execute('''SELECT modality,source,adapter,at,claims_json,confidence,verification
                    FROM capability_observations WHERE owner=? AND space=? AND id=?''',(owner,space,id)).fetchone()
            if old:
                if tuple(old)==payload:return {'status':'unchanged'}
                raise WorldCoreError('observation id reused for different contents')
            self.db.execute('INSERT INTO capability_observations VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (owner,space,id,*payload))
        return {'status':'recorded','trusted_as_instructions':False,'data_type':record['modality'],
                'notice':'a host adapter is required to actually perceive or navigate'}

    def explain_observation(self,owner,id,*,space='default'):
        owner,space=_valid_atom(owner,'owner'),_valid_atom(space,'space')
        with self.lock:
            r=self.db.execute('''SELECT * FROM capability_observations WHERE owner=? AND space=? AND id=?''',(owner,space,id)).fetchone()
        if not r:return None
        d=dict(r);d['claims']=json.loads(d.pop('claims_json'));d.pop('owner');d.pop('space')
        return d

    def record_skill_feedback(self,owner,id,skill,successful,reason,*,space='default',at=None):
        from .engine import WorldCoreError, _when
        from .intelligence import _txt
        owner,space,id,skill=map(lambda x:_valid_atom(x,'identifier'),(owner,space,id,skill))
        if type(successful) is not bool:raise WorldCoreError('expected boolean result')
        at=_when(at);reason=_txt(reason,500)
        with self._transaction():
            old=self.db.execute('SELECT successful,reason,at FROM skill_feedback WHERE owner=? AND space=? AND id=?',(owner,space,id)).fetchone()
            if old:
                if tuple(old)==(int(successful),reason,at):return {'status':'unchanged'}
                raise WorldCoreError('feedback is immutable; use a distinct id for corrections')
            self.db.execute('INSERT INTO skill_feedback VALUES(?,?,?,?,?,?,?)',
                            (owner,space,id,skill,at,int(successful),reason))
        return {'status':'recorded'}

    def suggest_with_uncertainty(self,domain,summary,evidence,*,confidence=None):
        """Advisory text payload, never a diagnosis, therapy, order, or psychological label.

        Confidence is descriptive if present, not calibrated. External host must
        enforce professional review and execution permissions.
        """
        from .engine import WorldCoreError
        from .intelligence import _txt
        if domain not in ('medicine','psychology','finance','crypto','sports_science','general'):
            raise WorldCoreError('unsupported advice domain')
        summary=_txt(summary,800)
        if not isinstance(evidence,list) or not evidence or len(evidence)>12 or any(not isinstance(x,dict) or not x.get('url') for x in evidence):
            raise WorldCoreError('recommendations require attributable evidence')
        if confidence is not None and (type(confidence) not in (float,int) or not 0<=confidence<=1):
            raise WorldCoreError('invalid confidence')
        notices={
          'medicine':'Informazione orientativa, non diagnosi o prescrizione. Consultare un professionista sanitario; urgenze richiedono assistenza immediata.',
          'psychology':'Ipotesi generali, non diagnosi individuale o deduzione di tratti privati.',
          'finance':'Non è un segnale operativo o rendimento garantito; verifica rischio, condizioni di mercato e professionisti autorizzati.',
          'crypto':'Non è un segnale operativo o rendimento garantito; possibile perdita totale del capitale.',
          'sports_science':'Informazione generale: personalizzazione e carichi richiedono verifiche adeguate.',
          'general':'Proposta soggetta a verifica delle fonti e del contesto.'}
        return {'kind':'advisory','domain':domain,'suggestion':summary,'evidence':evidence,
                'confidence':confidence,'confidence_calibrated':False,'notice':notices[domain],
                'authorized_action':False}
