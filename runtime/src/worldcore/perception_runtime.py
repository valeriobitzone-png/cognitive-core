"""Raw-media evidence extractors. SMALL, BOUNDED, NO GENERAL IMAGE/SPEECH RECOGNITION.

Digit recognizer: sklearn digits benchmark; exported decision forest for pure-Python inference.
Audio: DTMF dual-tone signal detector, NOT speech recognition.
Video: simple frame-change detector, NOT object semantics.
All paths are trusted host-only; never expose file paths from unauthenticated MCP calls.
"""
from __future__ import annotations
import json, math, wave
from pathlib import Path
from functools import lru_cache

MAX_MEDIA_BYTES=8*1024*1024

@lru_cache(maxsize=4)
def _read_model(path=None):
    filename=Path(path) if path else Path(__file__).with_name('data')/'digit_forest.json'
    return json.loads(filename.read_text(encoding='utf-8'))

def _tree_predict(nodes, features):
    idx=0
    while nodes[idx]['feature']>=0:
        n=nodes[idx]
        idx=n['left'] if features[n['feature']]<=n['threshold'] else n['right']
    return nodes[idx]['proba']

def digit_from_pixels(pixels, model_path=None, min_confidence=.55):
    if len(pixels)!=64 or not all(isinstance(x,(int,float)) and math.isfinite(x) and 0<=x<=16 for x in pixels):
        raise ValueError('expected 64 pixels in [0,16]')
    obj=_read_model(model_path)
    votes=[_tree_predict(tree,pixels) for tree in obj['trees']]
    mean=[sum(v[k] for v in votes)/len(votes) for k in range(10)]
    winner=max(range(10),key=lambda i:mean[i]); confidence=mean[winner]
    return {'digit':winner if confidence>=min_confidence else None,'confidence':round(confidence,5),
            'abstained':confidence<min_confidence,'model':'sklearn-digits-8x8-forest',
            'scope':'handwritten 8x8 digits only; no natural-image semantic recognition'}

def digit_from_image(image_path, model_path=None):
    from PIL import Image,ImageOps
    path=Path(image_path)
    if path.stat().st_size>MAX_MEDIA_BYTES:raise ValueError('image too large')
    with Image.open(path) as img:
        gray=ImageOps.grayscale(img)
        if gray.size!=(8,8):raise ValueError('trained only on preprocessed 8x8 digit images')
        pixels=[int(round(v/16)) for v in list(gray.get_flattened_data())]
    return digit_from_pixels(pixels,model_path)

_DTMF={(697,1209):'1',(697,1336):'2',(697,1477):'3',(770,1209):'4',(770,1336):'5',
       (770,1477):'6',(852,1209):'7',(852,1336):'8',(852,1477):'9',(941,1209):'*',
       (941,1336):'0',(941,1477):'#'}

def detect_dtmf_wav(path):
    import numpy as np
    path=Path(path)
    if path.stat().st_size>MAX_MEDIA_BYTES:raise ValueError('audio too large')
    with wave.open(str(path),'rb') as wav:
        if wav.getnchannels()!=1 or wav.getsampwidth()!=2:raise ValueError('mono PCM16 WAV required')
        sr=wav.getframerate()
        if sr not in (8000,16000):raise ValueError('8 or 16 kHz required')
        raw=wav.readframes(min(wav.getnframes(),sr*2))
    arr=np.frombuffer(raw,dtype='<i2').astype(float)
    if len(arr)<sr//10 or np.sqrt(np.mean(arr**2))<100: return {'key':None,'status':'abstained','scope':'DTMF only, NOT ASR'}
    arr=arr[:min(len(arr),sr)]
    x=arr*np.hanning(len(arr)); spectrum=abs(np.fft.rfft(x)); f=np.fft.rfftfreq(len(arr),1/sr)
    energy={hz:float(max(spectrum[abs(f-hz)<8],default=0.0)) for pair in _DTMF for hz in pair}
    lows=[697,770,852,941]; highs=[1209,1336,1477]
    a=max(lows,key=energy.get);b=max(highs,key=energy.get)
    other_l=max([energy[h] for h in lows if h!=a]);other_h=max([energy[h] for h in highs if h!=b]);noise=float(np.median(spectrum))+1e-9
    valid=energy[a]>max(2.0*other_l,15*noise) and energy[b]>max(2.0*other_h,15*noise)
    return {'key':_DTMF.get((a,b)) if valid else None,'status':'recognized' if valid else 'abstained',
            'scope':'DTMF only, NOT spoken language'}

def detect_video_change(frames, threshold=10.0):
    """Take trusted numpy image arrays. Does NOT name objects or understand a scene."""
    import numpy as np
    frames=list(frames)
    if len(frames)<2 or len(frames)>120: raise ValueError('2-120 frames required')
    base=[]
    for frame in frames:
        arr=np.asarray(frame,dtype=np.float32)
        if arr.ndim not in (2,3) or arr.size>1920*1080*4:raise ValueError('invalid frame')
        base.append(arr)
    if any(a.shape!=base[0].shape for a in base):raise ValueError('frame dimensions mismatch')
    changes=[float(np.abs(b-a).mean()) for a,b in zip(base,base[1:])]
    return {'mean_frame_delta':round(sum(changes)/len(changes),5),
            'motion_proxy':sum(changes)/len(changes)>=threshold,
            'scope':'pixel changes only; not action or object recognition'}

def detect_video_change_file(file_path, max_frames=60):
    """Decode trusted local video frames through OpenCV; pixel-motion proxy only.

    WARNING: untrusted video can exploit media decoders. Host must sandbox this
    handler and never expose arbitrary file paths to a public MCP client.
    """
    import cv2
    p=Path(file_path)
    if not p.is_file() or p.stat().st_size>MAX_MEDIA_BYTES:
        raise ValueError('missing or oversize video')
    cap=cv2.VideoCapture(str(p))
    frames=[]
    try:
        while len(frames)<max_frames:
            ok,frame=cap.read()
            if not ok:break
            frames.append(cv2.cvtColor(cv2.resize(frame,(64,64)),cv2.COLOR_BGR2GRAY))
    finally:
        cap.release()
    if len(frames)<2:return {'status':'abstained','reason':'not_enough_frames'}
    return {'status':'observed','frames':len(frames),**detect_video_change(frames,threshold=10.0)}
