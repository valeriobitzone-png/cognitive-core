from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'esperimenti-2026-11-11'))
import bench_models as b
b.ROOT=ROOT
b.MODELS.update({'rizzo17':Path('/Volumes/AMBRO/models/rizzo-flow/rizzo-flow-1.7b/spark-x2.5-1.7b-rizzo-flow-lora-q8_0.gguf'),'rizzo4':Path('/Volumes/AMBRO/models/rizzo-flow/rizzo-flow/spark-x2.5-4b-rizzo-flow-lora-q4_k_m.gguf')})
b.run(sys.argv[1])
