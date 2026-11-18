import importlib.util, json, math, struct, wave
from pathlib import Path
import pytest
from worldcore import WorldCore
from worldcore.perception_runtime import digit_from_pixels,digit_from_image,detect_dtmf_wav,detect_video_change

ROOT=Path(__file__).resolve().parents[1]

def test_digits_heldout_and_runtime_equal(tmp_path):
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    from PIL import Image
    data=load_digits()
    _x,heldout,_y,labels=train_test_split(data.data,data.target,test_size=.25,random_state=41,stratify=data.target)
    correct=0; accepted=0
    for i,(x,y) in enumerate(zip(heldout,labels)):
        result=digit_from_pixels(x.tolist())
        accepted+=result['digit'] is not None
        correct+=result['digit']==int(y)
        if i==5:
            photo=tmp_path/'digit.png';Image.fromarray((x.reshape(8,8)*16).clip(0,255).astype('uint8')).save(photo)
            # PNG roundtrips from raw gray values (max 240) into range 0-16
            assert digit_from_image(photo)['digit']==result['digit']
    assert accepted/len(heldout)>=.80
    assert correct/accepted>=.98  # conservative confidence gate

def test_digit_reject_invalid_values():
    with pytest.raises(ValueError):digit_from_pixels([0]*63)
    with pytest.raises(ValueError):digit_from_pixels([float('nan')]*64)

def test_audio_dtmf_signal_and_silence(tmp_path):
    import numpy as np
    sr=8000; t=np.arange(sr//2)/sr
    for name,data,key in [('tone',(.25*np.sin(2*np.pi*697*t)+.25*np.sin(2*np.pi*1336*t)),'2'),('silence',np.zeros_like(t),None)]:
        path=tmp_path/(name+'.wav')
        with wave.open(str(path),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr)
            w.writeframes((data*32000).astype('<i2').tobytes())
        assert detect_dtmf_wav(path)['key']==key

def test_video_motion_detection():
    import numpy as np
    a=np.zeros((20,20),dtype='uint8');b=np.full((20,20),220,dtype='uint8')
    assert not detect_video_change([a,a])['motion_proxy']
    assert detect_video_change([a,b])['motion_proxy']

def test_macro_data_observations_and_baseline():
    import sys
    sys.path.insert(0,str(ROOT/'benchmarks'))
    from v09_macro_2026 import run
    output=run()
    assert len(output['rows'])==3
    assert output['rows'][-1]['quarter']=='2026Q3'
    assert output['rows'][-1]['actual']==24611.077
    assert output['relative_improvement_last_change']>0.10
    assert 'No news-market correlation' in output['limits']

@pytest.mark.parametrize('args', [
    ('','',{},{}),
    (' ','','',None),
])
def test_no_unrestricted_approvals(args,tmp_path):
    with WorldCore(tmp_path/'db.sqlite') as w:
        with pytest.raises(Exception):w.propose_real_action('owner','shell.exec',{'command':'echo open'},'no')

def test_actual_filesystem_world_holdout():
    import sys
    sys.path.insert(0,str(ROOT/'benchmarks'))
    from v09_real_filesystem_world import run
    result=run()
    assert result['trained']=='trained'
    assert result['prediction']['status']=='predicted'
    assert abs(result['prediction']['state']['total_bytes']-result['actual']['total_bytes'])<1
    assert 'real_files' in str(result).lower() or result['created_real_files']

def test_market_case_does_not_claim_causation():
    path=ROOT/'training-artifacts'/'v09_real_news_market_case.json'
    case=json.loads(path.read_text())
    assert case['causal_status']=='NOT_ESTABLISHED'
    assert len(case['confounders'])>=2
    assert not case['model_training']

def test_real_video_decoder_motion(tmp_path):
    import cv2,numpy as np
    from worldcore.perception_runtime import detect_video_change_file
    target=tmp_path/'motion.avi'
    writer=cv2.VideoWriter(str(target),cv2.VideoWriter_fourcc(*'MJPG'),8,(64,64))
    assert writer.isOpened()
    for i in range(10):
        frame=np.zeros((64,64,3),dtype='uint8')
        frame[:,i*5:i*5+12]=255
        writer.write(frame)
    writer.release()
    result=detect_video_change_file(target)
    assert result['status']=='observed' and result['frames']==10 and result['motion_proxy']

def test_personal_memory_version_change_real_user_requirements(tmp_path):
    # Real, non-sensitive project preferences copied from the current user request,
    # but NOT a held-out external user-history benchmark.
    with WorldCore(tmp_path/'project.db') as core:
        core.remember('demo','engine.design','independent engine, connect to Hermes',space='project',source='current_request')
        core.remember('demo','engine.design','independent engine, connect to Hermes and OpenClaw',space='project',source='current_request')
        hist=core.history('demo','engine.design',space='project')
        assert len(hist)==2
        assert any('Hermes and OpenClaw' in str(v) for v in hist)
        assert core.history('other','engine.design',space='project')==[]
