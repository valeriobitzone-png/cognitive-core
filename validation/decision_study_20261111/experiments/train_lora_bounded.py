import json,os,sys,time
from pathlib import Path
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import mlx.core as mx
mx.set_memory_limit(6_000_000_000)
mx.set_cache_limit(300_000_000)
from mlx_lm.lora import main
began=time.monotonic()
try:main()
finally:
 print(json.dumps({'elapsed_seconds':time.monotonic()-began,'mlx_peak_bytes':mx.get_peak_memory(),
                   'limit_bytes':6_000_000_000}),flush=True)
