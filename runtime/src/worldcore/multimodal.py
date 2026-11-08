"""Privacy-preserving, local and bounded multimodal feature extraction.

Observes simple measurable features, not semantic vision, ASR, or autonomous
web navigation. LLM/vision host adapter provides semantic assertions separately.
"""
from __future__ import annotations
import io,math,struct,wave
from html.parser import HTMLParser


def png_features(raw:bytes):
    """PNG header features only. Full pixel understanding requires a vision provider."""
    if not isinstance(raw,bytes) or len(raw)>8_000_000 or len(raw)<33:
        raise ValueError('bounded PNG bytes required')
    if raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR':raise ValueError('not PNG')
    w,h=struct.unpack('>II',raw[16:24])
    if not 1<=w<=10000 or not 1<=h<=10000 or w*h>50_000_000:raise ValueError('invalid dimensions')
    return {'modality':'image','features':{'width':w,'height':h,'aspect_ratio':round(w/h,6),
            'source_bytes':len(raw)},'semantic_recognition':False,
            'warning':'Header-only; cannot identify objects or scenes'}


def wav_features(raw:bytes):
    """WAV signal envelope; bounded duration and PCM sample width (8/16bit)."""
    if not isinstance(raw,bytes) or len(raw)>8_000_000:raise ValueError('bounded WAV bytes required')
    with wave.open(io.BytesIO(raw),'rb') as audio:
        channels=audio.getnchannels();rate=audio.getframerate();count=audio.getnframes();width=audio.getsampwidth()
        if width not in (1,2) or channels not in (1,2) or not 8000<=rate<=192000 or count/rate>30:
            raise ValueError('unsupported bounded PCM WAV')
        pcm=audio.readframes(count)
    if width==1:values=[(v-128)/128 for v in pcm]
    else:values=[v[0]/32768 for v in struct.iter_unpack('<h',pcm)]
    rms=math.sqrt(sum(v*v for v in values)/max(1,len(values)))
    return {'modality':'audio','features':{'duration_seconds':round(count/rate,4),
       'sample_rate':rate,'channels':channels,'rms':round(rms,6)},'speech_transcription':False,
       'warning':'Signal-only; cannot recognize speech, speaker, or emotion'}


class _Page(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.title='';self.intitle=False;self.links=0;self.forms=0
    def handle_starttag(self,tag,attrs):
        if tag=='title':self.intitle=True
        if tag=='a':self.links+=1
        if tag=='form':self.forms+=1
    def handle_endtag(self,tag):
        if tag=='title':self.intitle=False
    def handle_data(self,data):
        if self.intitle:self.title=(self.title+data)[:160]


def html_features(html):
    """Parse supplied HTML; never fetch URLs, run JavaScript, or trust HTML text as commands."""
    if not isinstance(html,str) or len(html)>200_000:raise ValueError('bounded HTML required')
    p=_Page();p.feed(html)
    return {'modality':'web','features':{'links':p.links,'forms':p.forms,'has_title':int(bool(p.title))},
            'metadata':{'title':p.title},'browser_navigation':False,'trusted_as_instructions':False}


def combine_numeric_observations(records):
    """Combines typed numeric sensor features with their source/provenance.

    Does not infer an event across modalities; use an authorized semantic adapter.
    """
    if not isinstance(records,list) or not 1<=len(records)<=12:raise ValueError('1..12 modality observations required')
    combined={};sources=[]
    for i,rec in enumerate(records):
        if not isinstance(rec,dict) or rec.get('modality') not in ('image','audio','web','sensor','map','3d','text'):
            raise ValueError('invalid observation')
        src=rec.get('source')
        if not isinstance(src,str) or not src or len(src)>160:raise ValueError('source required')
        features=rec.get('features')
        if not isinstance(features,dict) or len(features)>20:raise ValueError('features required')
        for key,val in features.items():
            if not isinstance(key,str) or not key.isidentifier():raise ValueError('invalid feature name')
            if type(val) not in (int,float) or not math.isfinite(val):raise ValueError('numeric finite features required')
            combined[f'm{i}_{rec["modality"]}_{key}']=float(val)
        sources.append(src)
    return {'state':combined,'sources':sources,'verified_by_host':False,
            'note':'Coarse numeric features only; no semantic multimodal understanding'}
