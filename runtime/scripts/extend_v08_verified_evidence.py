"""Manually reconciled repository file hashes from direct connected GitHub reads.

All records are partial spot inspections, not a comprehensive quality audit.
"""
import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'catalog/reviewed_evidence_v08.json'
a=json.loads(p.read_text()); old={r['repo'].lower():r for r in a['records']}
D={
'danijar/dreamerv3':('MIT',{'license':('LICENSE','80bb3c8ed0c268d898f1eb4c42350e7417a94e53'),'source':('dreamerv3/agent.py','0cada34bbd87e6c3002522db244d1fb2c8896fb1'),'tests':('embodied/perf/test_driver.py','3c90dd212bbdf2e03b0c4804329529a09f336b53')}),
'modelcontextprotocol/python-sdk':('MIT',{'license':('LICENSE','3d48435454b105021b4f777c11b6b07d8d2ffea3')}),
'opencv/opencv':('Apache-2.0',{'license':('LICENSE','d645695673349e3947e8e5ae42332d0ac3164cd7'),'source':('modules/core/src/matrix.cpp','da63dc8e9a1ce0a0bfa609cb33e7cf4fc10f1b32'),'tests':('modules/core/test/test_mat.cpp','7c6731a265875139370ed6ee2cc95b2e604acfa5')}),
'microsoft/qlib':('MIT',{'license':('LICENSE','9e841e7a26e4eb057b24511e7b92d42b257a80e5'),'source':('qlib/contrib/model/pytorch_lstm.py','3ba09097acd33bcab38a5b611c36fc0250c2b3a5')}),
'FreeCAD/FreeCAD':('LGPL-2.1',{'license':('LICENSE','bc0390e98c98f2ad3ab7decdb82b4d57d7f850d4'),'source':('src/App/Document.cpp','9b2c53055d56e4f8ce1137ad85cfbc4bd2afb4c8'),'tests':('src/Mod/CAM/CAMTests/TestPostProcessor.py','1f435c18de823d12b031216715df06e4610891db')}),
'openscad/openscad':('NOT_VERIFIED',{}),
'n8n-io/n8n':('NOT_VERIFIED',{'source':('packages/cli/src/commands/start.ts','9bc307dce3ad1062dd20f46eb1bd44ae64e8dfab')}),
'AI4Finance-Foundation/FinRL':('MIT',{'license':('LICENSE','cbeb60a100b33079b5c90102fb89b4f9f229437c'),'source':('finrl/agents/stablebaselines3/models.py','49ddbeae5242af27623243688b259d657feaf3a8')}),
'huggingface/lerobot':('Apache-2.0',{'license':('LICENSE','93baf0c18936131979fdda6a38536cbcef0efccb'),'source':('src/lerobot/robots/robot.py','fa61ce9cee79f3593eb2980a0742e56b9eb3b180')}),
'py-why/dowhy':('MIT',{'license':('LICENSE','4c2f3418f06a299577362f7738e26662c2211849'),'source':('dowhy/causal_model.py','daa59dbf876995cd649dcfba74afaa1de6b527e9'),'tests':('tests/causal_estimators/test_linear_regression_estimator.py','751a7726015a18ec1d61aa4d7151ee2375c84c05'),'ci':('.github/workflows/ci.yml','d9322d8daca20aa35573675c47762443ab57da52')})}
for repo,(lic,ev) in D.items():
    branch='master' if repo in ['n8n-io/n8n','AI4Finance-Foundation/FinRL'] else '5.x' if repo=='opencv/opencv' else 'main'
    entry={'repo':repo,'license_detected':lic,'evidence':{
        k:{'path':path,'sha':sha,'url':f'https://github.com/{repo}/blob/{branch}/{path}'}
        for k,(path,sha) in ev.items()},
      'screen_status':'incomplete_source_quality_review' if ev else 'not_verified',
      'source_review_scope':'Selected files only; no full code or dependency security review',
      'tests_executed':False,'security_audit_complete':False,
      'license_reuse_cleared':False,'autonomous_code_execution_allowed':False,
      'used_to_train_weights':False}
    old[repo.lower()]=entry
# Do not imply network source pass for unverified OpenSCAD license.
a['records']=list(old.values())
a['warning']='26 sampled repositories, two of those lack verified license/source; NO full audit or auto integration'
p.write_text(json.dumps(a,ensure_ascii=False,indent=2))
print('records',len(a['records']))
