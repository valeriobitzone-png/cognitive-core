"""Read-only pure-Python inference for bounded offline-trained decision forests.

Models must be trained externally by an operator. No pickle, arbitrary code,
network, dataset import or autonomous retraining in the agent runtime.
"""
from __future__ import annotations
import json
import math
import struct
from .learning import _scope, _feature_names, _vector


def _validate(payload):
    from .engine import WorldCoreError
    required={'format','names','trees','training_rows','source'}
    if not isinstance(payload,dict) or not required.issubset(payload) or set(payload)-required-{'raw_names','scaler'}:
        raise WorldCoreError('invalid ensemble model envelope')
    if payload['format']!='worldcore.binary_forest.v1':raise WorldCoreError('unknown model format')
    _feature_names(payload['names'])
    if 'scaler' in payload or 'raw_names' in payload:
        if 'scaler' not in payload or 'raw_names' not in payload:
            raise WorldCoreError('raw transform must include both scaler and names')
        _feature_names(payload['raw_names'])
        if len(payload['raw_names'])!=len(payload['names']):
            raise WorldCoreError('raw schema mismatch')
        sc=payload['scaler']
        if not isinstance(sc,dict) or set(sc)!={'min','max'}:
            raise WorldCoreError('invalid raw scaler')
        if not isinstance(sc['min'],list) or not isinstance(sc['max'],list) or len(sc['min'])!=len(payload['names']) or len(sc['max'])!=len(payload['names']):
            raise WorldCoreError('invalid scaler dimensions')
        for mn,mx in zip(sc['min'],sc['max']):
            if type(mn) not in (float,int) or type(mx) not in (float,int) or not math.isfinite(mn) or not math.isfinite(mx) or mx<mn:
                raise WorldCoreError('invalid scaler bounds')
    if type(payload['training_rows']) is not int or not 30<=payload['training_rows']<=10_000_000:
        raise WorldCoreError('invalid training count')
    if not isinstance(payload['source'],str) or not 1<=len(payload['source'])<=512:
        raise WorldCoreError('source dataset provenance missing')
    if not isinstance(payload['trees'],list) or not 1<=len(payload['trees'])<=128:
        raise WorldCoreError('ensemble requires 1..128 trees')
    total=0
    for tree in payload['trees']:
        if not isinstance(tree,list) or not 1<=len(tree)<=2048:
            raise WorldCoreError('invalid tree length')
        total+=len(tree)
        if total>80000:raise WorldCoreError('too many forest nodes')
        for i,node in enumerate(tree):
            if not isinstance(node,list) or len(node)!=4:raise WorldCoreError('invalid node shape')
            feature,threshold,left,right=node
            if feature==-1:
                if not isinstance(threshold,(float,int)) or not math.isfinite(threshold) or not 0<=threshold<=1:
                    raise WorldCoreError('invalid leaf probability')
                if left!=-1 or right!=-1:raise WorldCoreError('leaf cannot have children')
            elif type(feature) is not int or not 0<=feature<len(payload['names']):
                raise WorldCoreError('invalid decision feature')
            else:
                if not isinstance(threshold,(float,int)) or not math.isfinite(threshold):
                    raise WorldCoreError('invalid split threshold')
                if type(left) is not int or type(right) is not int or not i<left<len(tree) or not i<right<len(tree):
                    raise WorldCoreError('cyclic or out-of-bounds tree child')
    return payload


def _infer(model, xs):
    # scikit-learn decision trees internally cast sample features to float32.
    # Reproduce that rounding to prevent boundary disagreement.
    xs=[struct.unpack("f",struct.pack("f",float(x)))[0] for x in xs]
    probabilities=[]
    for tree in model['trees']:
        node=0
        while True:
            feat,thr,left,right=tree[node]
            if feat==-1:
                probabilities.append(float(thr));break
            node=left if xs[feat]<=thr else right
    return sum(probabilities)/len(probabilities)


class EnsembleMixin:
    def _init_ensemble_schema(self):
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ensemble_models'").fetchone():
            return
        self.db.execute('''CREATE TABLE IF NOT EXISTS ensemble_models (
          owner TEXT NOT NULL,space TEXT NOT NULL,model_id TEXT NOT NULL,
          payload TEXT NOT NULL,created_at TEXT NOT NULL,
          PRIMARY KEY(owner,space,model_id))''')

    def import_ensemble(self,owner: str,model_id: str,payload: dict,*,space: str='default'):
        from .engine import WorldCoreError,utcnow
        scope=_scope(owner,space,model_id)
        _validate(payload)
        encoded=json.dumps(payload,separators=(',',':'),allow_nan=False)
        if len(encoded)>5000000:raise WorldCoreError('ensemble exceeds 5MB')
        with self._transaction():
            try:self.db.execute('INSERT INTO ensemble_models VALUES(?,?,?,?,?)',(*scope,encoded,utcnow()))
            except __import__('sqlite3').IntegrityError as exc:
                raise WorldCoreError('model exists; refusing silent overwrite') from exc
        return {'model_id':model_id,'trees':len(payload['trees']),'features':payload['names'],
                'training_rows':payload['training_rows'],'source':payload['source']}

    def predict_raw_ensemble(self, owner: str, model_id: str, features: dict, *, space: str='default'):
        from .engine import WorldCoreError
        scope=_scope(owner,space,model_id)
        with self.lock:
            row=self.db.execute('SELECT payload FROM ensemble_models WHERE owner=? AND space=? AND model_id=?',scope).fetchone()
        if not row:raise WorldCoreError('model not found')
        model=json.loads(row['payload'])
        if 'scaler' not in model:raise WorldCoreError('model has no raw feature scaler')
        names=model['raw_names']
        if not isinstance(features,dict) or set(features)!=set(names):
            raise WorldCoreError('raw features must match schema')
        xs=[];clipped=0
        for name,mn,mx in zip(names,model['scaler']['min'],model['scaler']['max']):
            val=features[name]
            if type(val) not in (int,float) or not math.isfinite(val):
                raise WorldCoreError('raw feature must be finite number')
            normalized=(val-mn)/max(mx-mn,1e-12)
            if not 0<=normalized<=1:clipped+=1
            xs.append(max(0.0,min(1.0,normalized)))
        return {'model_id':model_id,'probability':_infer(model,xs),'status':'out_of_training_range' if clipped else 'ready',
                'features_clipped':clipped,'source':model['source'],'executed':False,
                'warning':'extrapolation can be unreliable; associations not causal'}

    def predict_ensemble(self,owner: str,model_id: str,features: dict,*,space: str='default'):
        from .engine import WorldCoreError
        scope=_scope(owner,space,model_id)
        with self.lock:
            r=self.db.execute('SELECT payload FROM ensemble_models WHERE owner=? AND space=? AND model_id=?',scope).fetchone()
        if not r:raise WorldCoreError('model not found')
        model=json.loads(r['payload'])
        xs=_vector(features,model['names'])
        p=_infer(model,xs)
        return {'model_id':model_id,'probability':p,'status':'ready','trees':len(model['trees']),
                'source':model['source'],'executed':False,
                'warning':'trained numerical classifier; NOT calibrated or causal; no autonomous action'}
