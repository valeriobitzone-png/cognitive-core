"""Evidence-grounded multimodal state fusion, not an on-device vision/speech LLM.

A trusted host performs image understanding, ASR, OCR or text extraction.
WorldCore consumes typed grounded claims, retains provenance and contradiction,
and declines to assert agreement when modalities disagree.
"""
from __future__ import annotations
import json
import math
import re
import uuid
from .worldmodel import _valid_atom

_MODALITIES={'image','audio','text','web','map','3d','sensor'}
_LABEL=re.compile(r'^[A-Za-z0-9 _./:-]{1,100}$')

class SemanticFusionMixin:
    def _init_semantic_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS semantic_observations(
          id TEXT PRIMARY KEY,owner TEXT NOT NULL,space TEXT NOT NULL,context TEXT NOT NULL,
          modality TEXT NOT NULL,entity TEXT NOT NULL,attribute TEXT NOT NULL,
          value TEXT NOT NULL,confidence REAL NOT NULL,source TEXT NOT NULL,
          host_verified INTEGER NOT NULL,at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS semantic_context_idx
            ON semantic_observations(owner,space,context,entity,attribute);
        ''')

    def record_semantic_observation(self,owner,context,claims,*,space='default',modality,source,
                                    verified_by_host=False,at=None):
        from .engine import WorldCoreError,_when,_text
        owner,space,context,source=[_valid_atom(x,'identifier') for x in (owner,space,context,source)]
        if modality not in _MODALITIES:raise WorldCoreError('unsupported modality')
        if not isinstance(claims,list) or not 1<=len(claims)<=20:raise WorldCoreError('1..20 claims required')
        if type(verified_by_host) is not bool:raise WorldCoreError('host_verified must be bool')
        clean=[]
        for item in claims:
            if not isinstance(item,dict) or set(item)!={'entity','attribute','value','confidence'}:
                raise WorldCoreError('claim schema requires entity, attribute, value, confidence')
            entity,attribute,value=item['entity'],item['attribute'],item['value']
            if not all(isinstance(x,str) and _LABEL.fullmatch(x) for x in [entity,attribute,value]):
                raise WorldCoreError('bounded semantic labels required')
            confidence=item['confidence']
            if type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1:
                raise WorldCoreError('invalid confidence')
            clean.append((entity.strip().lower(),attribute.strip().lower(),value.strip().lower(),float(confidence)))
        stamp=_when(at)
        with self._transaction():
            for entity,attribute,value,confidence in clean:
                self.db.execute('INSERT INTO semantic_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (uuid.uuid4().hex,owner,space,context,modality,entity,attribute,value,confidence,source,int(verified_by_host),stamp))
        return {'status':'recorded','count':len(clean),'host_verified':verified_by_host,'raw_perception_performed':False}

    def semantic_scene(self,owner,context,*,space='default',min_confidence=.5):
        owner,space,context=[_valid_atom(x,'identifier') for x in (owner,space,context)]
        if type(min_confidence) not in (int,float) or not 0<=min_confidence<=1:raise ValueError('invalid threshold')
        with self.lock:
            rows=self.db.execute('''SELECT modality,entity,attribute,value,confidence,source,host_verified,at
               FROM semantic_observations WHERE owner=? AND space=? AND context=? ORDER BY at,id''',
               (owner,space,context)).fetchall()
        groups={}
        for r in rows:
            k=(r['entity'],r['attribute'])
            groups.setdefault(k,[]).append(dict(r))
        results=[]
        for (entity,attribute),evidence in sorted(groups.items()):
            # Only verified host claims are eligible for an evidence-backed consensus.
            trusted=[e for e in evidence if e['host_verified'] and e['confidence']>=min_confidence]
            values={e['value'] for e in trusted}
            modalities={e['modality'] for e in trusted}
            sources={e['source'] for e in trusted}
            status='unsupported' if not trusted else 'conflict' if len(values)>1 else 'single_source' if len(sources)<2 or len(modalities)<2 else 'corroborated'
            results.append({'entity':entity,'attribute':attribute,'status':status,
                'value':next(iter(values)) if len(values)==1 else None,
                'sources':sorted(sources),'modalities':sorted(modalities),
                'evidence_count':len(evidence),'verified_count':len(trusted),
                'note':'Host-asserted semantics only. Corroboration is not independent ground truth.'})
        return {'context':context,'claims':results,'raw_media_decoded_semantically':False}
