import pytest
from worldcore import WorldCore,WorldCoreError

def forest():
    return {'format':'worldcore.binary_forest.v1','names':['x'],
        'trees':[[[0,.5,1,2],[-1,.1,-1,-1],[-1,.9,-1,-1]]],
        'training_rows':100,'source':'https://example.org/real-world-data'}

def test_forest_roundtrip(tmp_path):
    file=tmp_path/'f.db'
    with WorldCore(file) as w:
        w.import_ensemble('alice','classifier',forest(),space='workspace')
        assert abs(w.predict_ensemble('alice','classifier',{'x':.2},space='workspace')['probability']-.1)<1e-9
        assert abs(w.predict_ensemble('alice','classifier',{'x':.8},space='workspace')['probability']-.9)<1e-9
        with pytest.raises(WorldCoreError):w.predict_ensemble('bob','classifier',{'x':.8},space='workspace')
    with WorldCore(file) as w:
        assert w.predict_ensemble('alice','classifier',{'x':.8},space='workspace')['status']=='ready'

def test_malformed_trees_rejected(tmp_path):
    with WorldCore(tmp_path/'f.db') as w:
        p=forest();p['trees'][0][0]=[0,.5,0,1]
        with pytest.raises(WorldCoreError):w.import_ensemble('a','bad',p)
        p=forest();p['trees']=[[[-1,float('nan'),-1,-1]]]
        with pytest.raises(WorldCoreError):w.import_ensemble('a','bad',p)
        with pytest.raises(WorldCoreError):w.import_ensemble('a','bad',{'trees':[]})

def test_forest_no_overwrite(tmp_path):
    with WorldCore(tmp_path/'f.db') as w:
        w.import_ensemble('a','x',forest())
        with pytest.raises(WorldCoreError):w.import_ensemble('a','x',forest())

def test_raw_features_scaler_and_ood(tmp_path):
    p=forest();p['raw_names']=['raw_x'];p['scaler']={'min':[10.0],'max':[20.0]}
    with WorldCore(tmp_path/'f.db') as w:
        w.import_ensemble('a','f',p)
        assert w.predict_raw_ensemble('a','f',{'raw_x':12.0})['probability']==.1
        out=w.predict_raw_ensemble('a','f',{'raw_x':22.0})
        assert out['features_clipped']==1 and out['status']=='out_of_training_range'
        with pytest.raises(WorldCoreError):w.predict_raw_ensemble('a','f',{'raw_x':float('nan')})
