"""Deterministic candidate pool from results of GitHub repository searches 2026-10-30.

No claims of code audit, model training or licensing review. Search discovery only.
Curated to prefer relevant engineering and research repositories, not star rankings.
"""
from __future__ import annotations
import json
from pathlib import Path

GROUPS={
'world_models':'''danijar/dreamerv3 sailing-lab/sira Cveinnt/kepler QwenLM/Qwen-AgentWorld nicklashansen/tdmpc2 OpenDriveLab/Vista Tencent-Hunyuan/HunyuanWorld-1.0 Tencent-Hunyuan/HY-WorldPlay Tencent-Hunyuan/HunyuanWorld-Voyager Tencent-Hunyuan/HunyuanWorld-Mirror thu-ml/Motus thu-ml/Causal-Forcing PKU-YuanGroup/Helios nv-tlabs/lyra SkyworkAI/Matrix-Game inclusionAI/AWorld galilai-group/stable-worldmodel''',
'mcp_api':'''modelcontextprotocol/python-sdk modelcontextprotocol/typescript-sdk modelcontextprotocol/modelcontextprotocol''',
'agents':'''NousResearch/hermes-agent openclaw/openclaw langchain-ai/langgraph mem0ai/mem0 getzep/graphiti letta-ai/letta microsoft/autogen pydantic/pydantic-ai deepset-ai/haystack microsoft/agent-framework agentscope-ai/agentscope The-Pocket/PocketFlow langroid/langroid gptme/gptme HKUDS/nanobot langgenius/dify browser-use/browser-use strands-agents/harness-sdk MiroMindAI/MiroThinker Upsonic/Upsonic''',
'finance_crypto':'''AI4Finance-Foundation/FinGPT freqtrade/freqtrade ccxt/ccxt polakowo/vectorbt AI4Finance-Foundation/FinRL microsoft/qlib hummingbot/hummingbot openbq-org/OpenBB stefan-jansen/machine-learning-for-trading quantopian/zipline StockSharp/StockSharp Superalgos/Superalgos kernc/backtesting.py ranaroussi/quantstats PyPortfolio/PyPortfolioOpt jesse-ai/jesse firmai/financial-machine-learning questdb/questdb TA-Lib/ta-lib-python wilsonfreitas/awesome-quant Fincept-Corporation/FinceptTerminal''',
'news_history':'''koala73/worldmonitor sansan0/TrendRadar newsnext/newsnow codelucas/newspaper fhamborg/news-please Thysrael/Horizon JustAnotherArchivist/snscrape wikimedia/wikidata-query-rdf AllenInstitute/open-instruct allenai/scispacy HKUDS/LightRAG vesoft-inc/nebula dgraph-io/dgraph Graphify-Labs/graphify topoteretes/cognee HKUDS/DeepCode langfuse/langfuse''',
'psychology_neuro':'''psychopy/psychopy jspsych/jsPsych mne-tools/mne-python neuropsychology/NeuroKit.py brainflow-dev/brainflow braindecode/braindecode brian-team/brian2 snntorch/snntorch NeuroTechX/moabb SpikeInterface/spikeinterface fieldtrip/fieldtrip nengo/nengo FelixHenninger/lab.js crsh/papaja simonarvin/eyeloop NeuromatchAcademy/course-content''',
'medicine_biology':'''Project-MONAI/MONAI OHIF/Viewers Slicer/Slicer cornerstonejs/cornerstone InsightSoftwareConsortium/ITK facebookresearch/fastMRI AIM-Harvard/pyradiomics biopython/biopython google/deepvariant nextflow-io/nextflow sokrypton/ColabFold scverse/scanpy OpenGene/fastp lh3/minimap2 soedinglab/MMseqs2 broadinstitute/gatk rdkit/rdkit openmm/openmm rordenlab/dcm2niix''',
'sports':'''opensim-org/opensim-core PySport/kloppy hudl/statsbombpy hudl/open-data davidpagnon/Sports2D simbody/simbody pyomeca/pyomeca ML-KULeuven/socceraction nflverse/nflfastR SoccerNet/sn-gamestate AtomScott/SportsLabKit UnravelSports/unravelsports roboflow/sports eddwebster/football_analytics pnxenopoulos/awpy''',
'maps_geospatial':'''QGIS/QGIS gboeing/osmnx geopandas/geopandas organicmaps/organicmaps CesiumGS/cesium keplergl/kepler.gl Turfjs/turf graphhopper/graphhopper uber/h3 tidwall/tile38 opengeos/GeoLibre hyperknot/openfreemap Project-OSRM/osrm-backend valhalla/valhalla mapillary/OpenSfM''',
'architecture_bim':'''FreeCAD/FreeCAD IfcOpenShell/IfcOpenShell DynamoDS/Dynamo opensourceBIM/BIMserver ThatOpen/web-ifc-viewer ThatOpen/web-ifc-three xeokit/xeokit-sdk iTwin/itwinjs-core xBimTeam/XbimEssentials xeokit/xeokit-bim-viewer openscad/openscad gumyr/build123d mingrammer/diagrams''',
'3d_printing':'''blender/blender prusa3d/PrusaSlicer bambulab/BambuStudio Ultimaker/Cura OrcaSlicer/OrcaSlicer MarlinFirmware/Marlin cnr-isti-vclab/meshlab slic3r/Slic3r huxingyi/dust3d Donkie/Spoolman maz iggy/bambuddy FreeCAD/FreeCAD alicevision/Meshroom nerfstudio-project/nerfstudio NVlabs/instant-ngp VAST-AI-Research/TripoSR openMVG/openMVG cdcseacave/openMVS facebookresearch/map-anything DLR-RM/BlenderProc''',
'vision_robotics':'''opencv/opencv ultralytics/ultralytics roboflow/supervision google-ai-edge/mediapipe CMU-Perceptual-Computing-Lab/openpose HumanSignal/label-studio graphdeco-inria/gaussian-splatting google-deepmind/mujoco bulletphysics/bullet3 ros2/ros2 huggingface/lerobot AtsushiSakai/PythonRobotics ArduPilot/ardupilot commaai/openpilot rerun-io/rerun google-deepmind/mujoco nasa-jpl/open-source-rover kornia/kornia''',
'social_marketing':'''gitroomhq/postiz-app growchief/growchief matomo-org/matomo mautic/mautic plausible/analytics n8n-io/n8n activepieces/activepieces qeeqbox/social-analyzer ScrapeCreators/social-media-research-skills leaperone/MultiPost-Extension trendex/social-app koala73/worldmonitor newsnext/newsnow news-please/news-please''',
'llm_nlp':'''huggingface/transformers huggingface/datasets explosion/spaCy RasaHQ/rasa google-research/bert hankcs/HanLP QwenLM/Qwen rasbt/LLMs-from-scratch vllm-project/vllm vllm-project/vllm-omni open-webui/open-webui lm-sys/FastChat langchain-ai/langchain huggingface/trl EleutherAI/lm-evaluation-harness EvolvingLMMs-Lab/lmms-eval''',
'ai_eval_security':'''langfuse/langfuse mlflow/mlflow promptfoo/promptfoo comet-ml/opik confident-ai/deepeval Arize-ai/phoenix NVIDIA/garak Giskard-AI/giskard-oss Helicone/helicone oumi-ai/oumi Tencent/AI-Infra-Guard facebookresearch/fastText microsoft/agent-governance-toolkit''',
'causal_science':'''py-why/dowhy uber/causalml py-why/EconML pgmpy/pgmpy py-why/causal-learn mckinsey/causalnex statsmodels/statsmodels pandas-dev/pandas scikit-learn/scikit-learn scipy/scipy pydata/xarray pytorch/pytorch matplotlib/matplotlib google-deepmind/mujoco''',
}

# Correct a whitespace spelling mistake in curated topic list; and drop a couple
# previously discovered names that were not exact tool-return names.
GROUPS['3d_printing']=GROUPS['3d_printing'].replace('maz iggy/bambuddy','maziggy/bambuddy')
GROUPS['social_marketing']=GROUPS['social_marketing'].replace('trendex/social-app ','').replace('news-please/news-please ','')
GROUPS['psychology_neuro']=GROUPS['psychology_neuro'].replace('snntorch/snntorch ','jeshraghian/snntorch ')

BASE=Path(__file__).resolve().parents[1]
old=json.loads((BASE/'catalog/repositories.json').read_text())
known={item['repo']:item for item in old}
for domain, chunk in GROUPS.items():
    for repo in chunk.split():
        if repo not in known:
            known[repo]={
              'repo':repo,'url':'https://github.com/'+repo,'domain':domain,
              'original_capability_summary':'Candidate for '+domain.replace('_',' ')+'; requires domain-specific code review',
              'verified':'GitHub repository search discovery 2026-10-30; README NOT CHECKED',
              'license_review':'NOT VERIFIED','code_quality_review':'NOT YET PERFORMED'}
items=sorted(known.values(),key=lambda x:(x['domain'],x['repo'].casefold()))
for item in items:
    if item['repo'] in {'modelcontextprotocol/python-sdk','modelcontextprotocol/typescript-sdk','modelcontextprotocol/modelcontextprotocol','AI4Finance-Foundation/FinGPT','danijar/dreamerv3','gitroomhq/postiz-app'}:
        item['verified']='README fetched in connected GitHub research 2026-10-30'
    item['selection_tier']='README_EXAMINED' if 'README fetched' in item.get('verified','') else 'GITHUB_DISCOVERED_ONLY'
    item['trained_on_code']=False
    item['quality_score']=None
    item['training_rights_cleared']=False
    item['quality_ranking_eligible']=False
out=BASE/'catalog/repository_candidates_v06.json';out.write_text(json.dumps(items,indent=2,ensure_ascii=False)+'\n')
print('Unique candidate repositories:',len(items))
from collections import Counter
print('Domains:',dict(Counter(x['domain'] for x in items)))
assert len(items)>=200
