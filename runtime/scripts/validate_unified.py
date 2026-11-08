"""Inspectable integration demo. Public web access requires --allow-public-web."""
import argparse
import json
from pathlib import Path
import tempfile

from cognitive_core import CognitiveCore, Settings
from cognitive_core.benchmark import evaluate


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-public-web',action='store_true')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='cognitive-unified-demo-') as home:
        core=CognitiveCore(Settings(home=home,namespace='demo',enable_web=args.allow_public_web,
                                    domain_allowlist=('docs.python.org',),max_web_requests_per_job=2,
                                    max_web_requests_per_day=2))
        try:
            greeting=core.observe({'text':'ciao'})
            zero_db=not list(Path(home).iterdir())
            assert greeting['action']=='WAIT' and zero_db
            event={'kind':'research_requested','question':'How does the Python JSON decoder work?',
                   'seed_urls':['https://docs.python.org/3/library/json.html']}
            first=core.observe(event)
            again=core.observe(event)
            assert first['topics']==again['topics'] and len(core.vault.pending_jobs())==1
            research=core.work_once()
            sources=[]
            for ident in research.get('sources',[]):
                document=core.vault.get_document(ident)
                sources.append({'id':ident,'url':document['source_url'],'sha256':document['sha256'],
                                'kind':document['kind'],'characters':len(document['text'])})
            core.worldcore.set_state('local','budget',100,space='demo')
            comparison=core.compare_futures('Compare preparation budget assumptions',[
                {'id':'wait','actions':[]},
                {'id':'prepare','actions':[{'op':'add','key':'budget','value':-5}]}],
                objectives=[{'key':'budget','direction':'minimize','scale':1}])
            assert comparison['action_executed'] is False
            assert core.worldcore.state('local',space='demo')['budget']==100
            assert len(core.worldcore.whatif_history('local',space='demo'))==1
            prediction=core.vault.predict(first['topics'][0],'Synthetic outcome will occur',.75,'demo only')
            score=core.vault.resolve_prediction(prediction,False,'Synthetic test observation')
            assert score==.5625
            benchmark=evaluate(Path(__file__).resolve().parents[1]/'examples/cognitive_core/decision_eval.jsonl',core.s)
            result={'greeting_no_databases':zero_db,'topic_deduplicated':True,'research':research,
                    'public_web_opted_in':args.allow_public_web,'source_metadata_only':sources,
                    'web_reservations':core.vault.usage('web_requests'),
                    'whatif':{'run_id':comparison['run_id'],'ranking':comparison['ranking'],
                              'action_executed':False,'original_budget':100},
                    'synthetic_prediction_brier':score,'decision_benchmark':benchmark,
                    'model_calls':0,'note':'public source collection is not verification of its claims'}
            if args.allow_public_web:
                assert research['status']=='done' and len(sources)==1, research
                assert result['web_reservations']==2
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,indent=2))
            print(json.dumps(result,indent=2))
        finally:
            core.close()


if __name__=='__main__':main()
