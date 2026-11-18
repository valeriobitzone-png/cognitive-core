"""Curated *directly retrieved* GitHub evidence (2026-10-30). Partial audit only.

No claims of full CI run, codebase review, active exploit scanning, or model training.
Every SHA below was returned by a direct GitHub file retrieval in this session.
"""
from pathlib import Path
import json,datetime
ROOT=Path(__file__).resolve().parents[1]
rows=[
 ('sailing-lab/sira','Apache-2.0','LICENSE','261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64','pyproject.toml','eb3630c07aa8bcdcaa701c3edc56f746b5c09e47',None,None,None,None),
 ('Cveinnt/kepler','MIT','LICENSE','d200e3420deaf83839ba6c79fcf52ad79b6a284f','harness/ws_tools/commit.py','077c8af9ca1335d4d92860b0162dbcab88296188',None,None,'.github/workflows/ci.yml','bfde051d510a67f7f37532fccdbc39932835b404'),
 ('getzep/graphiti','Apache-2.0','LICENSE','5feb0d9d299a1107adfa8331306b13cc0eff2d78','graphiti_core/graphiti.py','bd46a19e5f9ee129fb20df43dced053416c7e9f4',None,None,None,None),
 ('langchain-ai/langgraph','MIT','LICENSE','fc0602feecdd6748623c852ab534e1ca612673c7','libs/langgraph/langgraph/graph/state.py','9a87f16fa91a794b2e9be09352c1cb03ae89a90d','libs/langgraph/tests/test_pregel.py','0079b2a577be9bb6c8734c9a20472d9f2ef97eba',None,None),
 ('pydantic/pydantic-ai','MIT','LICENSE','1bf1f55e6d1736b499ded961ec6b94bfebb17aec','pydantic_ai_slim/pydantic_ai/agent/abstract.py','343781240096a78abc5ce2fdf2a1af00829bf519','tests/test_agent.py','1058eae300beb303b9bed0b7710f67a0d211f55f','.github/workflows/ci.yml','66dd7d6a650e197797d12730e790d6b89fcd8e64'),
 ('letta-ai/letta','Apache-2.0','LICENSE','f75c3422907f55d71685ae59afdc28498cde5a40',None,None,None,None,None,None),
 ('freqtrade/freqtrade','GPL-3.0','LICENSE','9cecc1d4669ee8af2ca727a5d8cde10cd8b2d7cc','freqtrade/freqtradebot.py','1087e90854d4b3233e05f23c9b80098538626b57','tests/test_main.py','0551def2d6bf9019a09966f9e2661e1ea16385ae','.github/workflows/ci.yml','1becb2ae7dacfc8c5f608508c2f762756cc72d16'),
 ('polakowo/vectorbt','Apache-2.0-with-Commons-Clause','LICENSE.md','1ecf7675862c3caede8c26bed7150c6c41036d45','vectorbt/portfolio/base.py','3cca3df3e097109c42f1294f852134f8476aadf5',None,None,None,None),
 ('gboeing/osmnx','UNKNOWN_LICENSE','',None,'osmnx/graph.py','3233e85983999bd8348757b8ac690455c5b3bc4e',None,None,None,None),
 ('geopandas/geopandas','BSD-3-Clause','LICENSE.txt','028603be2080134aa4817ed691fec3f449ffa609',None,None,None,None,None,None),
 ('Project-MONAI/MONAI','Apache-2.0','LICENSE','261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64','monai/networks/nets/unet.py','a4995ef7018f0d37f9c7d7bd23ad3c4db177daac','tests/integration/test_integration_unet_2d.py','706b0e0afbcc5af15d6f3f11c8746f7fcd5d6630',None,None),
 ('psychopy/psychopy','GPL-3.0','LICENSE','f288702d2fa16d3cdf0035b15a9fcbc552cd88e7','psychopy/visual/window.py','c601a6a4d8ffe575a3db7b793a397640b5c794c2',None,None,None,None),
 ('mne-tools/mne-python','BSD-3-Clause','LICENSE.txt','8e4a81bec1eb1d1c38bef305216fae3323a3ffbf',None,None,None,None,None,None),
 ('huggingface/transformers','Apache-2.0','LICENSE','68b7d66c97d66c58de883ed0c451af2b3183e6f3','src/transformers/models/bert/modeling_bert.py','ec4bb968fe0cc232bd83e78303594e31abcc6f71',None,None,None,None),
 ('scikit-learn/scikit-learn','BSD-3-Clause','COPYING','3d7ee432c15b685eaa654b6abe8f8e3ea8126a8d',None,None,None,None,None,None),
 ('gitroomhq/postiz-app','AGPL-3.0','LICENSE','24fd22792bf887200be9e1388c7b9d4782c6b3b2','apps/backend/src/main.ts','7f5523bde2575ffc4aca41f24fef37052cbe0209',None,None,'.github/workflows/build.yml','4738b6307920bff7ce3442345ac959e098f08fa9'),
]
out=[]
for repo,license_id,license_path,licsha,code,codesha,test,testsha,ci,cisha in rows:
  branch=('develop' if repo=='freqtrade/freqtrade' else 'dev' if repo in ('Project-MONAI/MONAI','psychopy/psychopy') else 'master' if repo=='polakowo/vectorbt' else 'main')
  checks={}
  for k,p,sha in [('license',license_path,licsha),('source',code,codesha),('tests',test,testsha),('ci',ci,cisha)]:
    if p and sha:checks[k]={'path':p,'sha':sha,'url':f'https://github.com/{repo}/blob/{branch}/{p}'}
  if repo=='polakowo/vectorbt':status='restricted_license_manual_review'
  elif license_id in ('GPL-3.0','AGPL-3.0'):status='copyleft_manual_review'
  elif all(x in checks for x in ('license','source','tests','ci')):status='source_screened_not_approved'
  else:status='incomplete_source_quality_review'
  out.append({'repo':repo,'license_detected':license_id,'evidence':checks,
     'screen_status':status,'source_review_scope':'Selected file(s) and small excerpt, NOT full code review',
     'tests_executed':False,'security_audit_complete':False,'license_reuse_cleared':False,
     'autonomous_code_execution_allowed':False,'used_to_train_weights':False})
(ROOT/'catalog/reviewed_evidence_v07.json').write_text(json.dumps({'as_of':'2026-10-30','records':out,
  'warning':'All 246 candidates remain quarantined for code execution; screening does not authorize integration.'},indent=2))
raw=json.loads((ROOT/'catalog/repository_candidates_v06.json').read_text())
checked={x['repo']:x['screen_status'] for x in out}
list_status=[{'repo':r['repo'],'domain':r.get('domain'),'audit_status':checked.get(r['repo'],'not_audited'),
              'can_install':False,'may_be_used_as_verified_skill':False} for r in raw]
(ROOT/'catalog/candidate_quarantine_v07.json').write_text(json.dumps(list_status,indent=2))
print(json.dumps({'candidate_count':len(raw),'direct_file_evidence_repos':len(out),
                  'source_code_retrieved':sum('source' in r['evidence'] for r in out),
                  'license_text_retrieved':sum('license' in r['evidence'] for r in out),
                  'code_test_ci_license_screened':sum(r['screen_status']=='source_screened_not_approved' for r in out),
                  'approved_for_execution':0}))
