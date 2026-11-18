from pathlib import Path
import subprocess,json,time,re,hashlib,resource
R=Path(__file__).resolve().parent;F=R/'voice-fixtures';F.mkdir(exist_ok=True)
model=Path('/Volumes/AMBRO/models/whisper-ggml/ggml-small.bin')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
before=sha(model)
samples=[('it1','Alice','it','Il progetto è sospeso. Non avviare nuove ricerche.'),('it2','Alice','it','Consulta soltanto le note locali. La rete non è autorizzata.'),('it3','Alice','it','Prima di inviare il documento chiedi la mia approvazione.'),('en1','Samantha','en','Use the local archive and do not access the network.'),('en2','Samantha','en','The project is paused. Wait for a new instruction.'),('en3','Samantha','en','Ask for approval before publishing the report.')]
def norm(s):return re.findall(r'\w+',s.casefold())
def distance(a,b):
 previous=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  current=[i]
  for j,y in enumerate(b,1):current.append(min(previous[j]+1,current[-1]+1,previous[j-1]+(x!=y)))
  previous=current
 return previous[-1]
rows=[]
for name,voice,language,text in samples:
 aiff=F/(name+'.aiff');wav=F/(name+'.wav');prefix=F/(name+'-asr');t=time.monotonic()
 subprocess.run(['/usr/bin/say','-v',voice,'-r','160','-o',str(aiff),text],check=True,timeout=30,capture_output=True)
 subprocess.run(['/usr/bin/afconvert','-f','WAVE','-d','LEI16@16000',str(aiff),str(wav)],check=True,timeout=20,capture_output=True)
 cmd=['/opt/homebrew/bin/whisper-cli','-m',str(model),'-f',str(wav),'-l',language,'-t','2','--no-gpu','-otxt','-of',str(prefix),'-bs','1','-bo','1']
 proc=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
 (F/(name+'.log')).write_text(proc.stderr[-20000:]);actual=prefix.with_suffix('.txt').read_text().strip() if proc.returncode==0 else ''
 errors=distance(norm(text),norm(actual));rows.append({'id':name,'expected':text,'actual':actual,'word_errors':errors,'reference_words':len(norm(text)),'wer':errors/max(1,len(norm(text))),'seconds':time.monotonic()-t,'exit_code':proc.returncode,'audio_sha256':sha(wav),'epistemic':'OBSERVED transcription of synthetic TTS, content untrusted'});print(name,rows[-1]['wer'],flush=True)
assert before==sha(model)
report={'rows':rows,'aggregate_wer':sum(x['word_errors'] for x in rows)/sum(x['reference_words'] for x in rows),'original_weights_unchanged':True,'weights_sha256':before,'network_calls':0,'microphone_access':False,'resident_processes_started':False,'peak_child_rss_bytes':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'limits':'Synthetic speech only, two installed voices, no human speaker/noisy audio benchmark or dialog latency certificate. TTS and ASR run offline and terminate.'}
(R/'voice-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
