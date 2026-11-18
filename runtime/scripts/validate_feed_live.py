"""Opt-in public-source end-to-end test. No private accounts or LLMs."""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
import tempfile

from cognitive_core import CognitiveCore, Settings


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--allow-public-web',action='store_true',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='feed-live-smoke-') as home:
        core=CognitiveCore(Settings(home=home,enable_web=True,namespace='live_smoke',
            domain_allowlist=('docs.python.org',),max_web_requests_per_job=2,max_web_requests_per_day=2))
        try:
            core.drive.upsert_project('core','Cognitive Core',['python','json','decoder'],1)
            stamp=datetime.now(timezone.utc).isoformat()
            event={'source_kind':'web','source_ref':'https://docs.python.org/3/library/json.html',
                   'occurred_at':stamp,'title':'Python JSON decoder reference',
                   'summary':'Read the public Python JSON decoder reference to inspect source ingestion.'}
            candidate=core.drive.ingest(event)
            core.worldcore.set_state('local','requests_left',2,space='live_smoke')
            simulation=core.drive.compare(candidate['opportunity_id'],[
                {'id':'defer','actions':[]},
                {'id':'read_source','actions':[{'op':'add','key':'requests_left','value':-2}]}],
                objectives=[{'key':'requests_left','direction':'maximize','scale':1}])
            assert core.worldcore.state('local',space='live_smoke')['requests_left']==2
            prepared=core.drive.prepare(.8)
            research=core.work_once()
            documents=[core.vault.get_document(ident) for ident in research.get('sources',[])]
            reserved=core.vault.usage('web_requests')
            result={'test':'actual public source, Drive → queue → fetch → ledger → WHAT IF reconciliation',
                    'candidate':candidate,'prepared':prepared,'research':research,
                    'documents':[{'id':d['id'],'url':d['source_url'],'sha256':d['sha256'],
                                  'characters':len(d['text']),'kind':d['kind']} for d in documents],
                    'requests_reserved':reserved,'world_state_unchanged':True,
                    'experiences':core.vault.db.execute('SELECT count(*) FROM experiences').fetchone()[0],
                    'human_usefulness_feedback':'pending; not inferred by test',
                    'private_accounts_used':False,'model_calls':0}
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,indent=2))
            assert research['status']=='done' and not research['errors']
            assert len(documents)==1 and reserved==2 and result['experiences']==1
            verified=core.worldcore.verify_whatif('local',simulation['run_id'],'read_source',
                {'requests_left':2-reserved},space='live_smoke',source='host_verified')
            assert verified['absolute_errors']['requests_left']==0
            result['whatif_verification']=verified
            args.output.write_text(json.dumps(result,indent=2))
            print(json.dumps(result,indent=2))
        finally:core.close()


if __name__=='__main__':main()
