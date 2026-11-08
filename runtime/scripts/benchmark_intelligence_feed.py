"""Replay a labelled synthetic feed; labels never enter the ingestion API."""
import argparse
import json
from pathlib import Path
import tempfile

from cognitive_core import CognitiveCore, Settings


def evaluate(fixture):
    with tempfile.TemporaryDirectory(prefix='intelligence-feed-') as home:
        core=CognitiveCore(Settings(home=home))
        try:
            for project in fixture['projects']:
                core.drive.upsert_project(project['id'],project['title'],project['keywords'],project['importance'])
            ids={};expected=set();duplicates=errors=0
            for sample in fixture['events']:
                try:
                    result=core.drive.ingest(sample['event'],now=sample['received_at'])
                except ValueError:
                    if not sample.get('expect_error'):raise
                    errors+=1;continue
                assert not sample.get('expect_error'),'future observation accepted'
                duplicates+=int(result['duplicate'])
                if result.get('opportunity_id'):ids[result['opportunity_id']]=sample['id']
                if sample.get('expected_selected'):expected.add(sample['id'])
                if sample.get('dismiss'):
                    core.drive.review(result['opportunity_id'],'dismissed','synthetic operator choice',now=sample['received_at'])
            projection=core.drive.briefing(as_of=fixture['as_of'],limit=5)
            selected={ids[item['id']] for item in projection['items']}
            precision=len(selected&expected)/len(selected) if selected else 0
            recall=len(selected&expected)/len(expected) if expected else 0
            assert selected==expected,(selected,expected)
            assert duplicates==1 and errors==1
            core.worldcore.set_state('local','research_cost',0)
            item=projection['items'][0]
            comparison=core.drive.compare(item['id'],[
                {'id':'defer','actions':[]},
                {'id':'read_source','actions':[{'op':'set','key':'research_cost','value':1}]}],
                objectives=[{'key':'research_cost','direction':'minimize','scale':1}])
            assert core.worldcore.state('local')['research_cost']==0
            assert comparison['action_executed'] is False
            # A later real-time comparison cannot appear in the historical briefing.
            assert all(i['whatif_run_id'] is None for i in core.drive.briefing(as_of=fixture['as_of'])['items'])
            assert core.drive.prepare(0)['jobs']==[]
            prepared=core.drive.prepare(.8,limit=1)
            assert len(prepared['jobs'])==1
            feedback=core.drive.record_outcome(item['id'],True,'synthetic-review-fixture')
            return {'scope':fixture['scope'],'events':len(fixture['events']),
                    'selected':sorted(selected),'expected':sorted(expected),
                    'precision_at_5':precision,'recall_at_5':recall,'duplicates':duplicates,
                    'future_observations_rejected':errors,'temporal_projection_checked':True,
                    'whatif_run_id':comparison['run_id'],'state_unchanged':True,
                    'capacity_gated':True,'prepared_jobs':len(prepared['jobs']),
                    'feedback':feedback,'model_calls':0,'web_requests':0,
                    'limitation':'lexical synthetic contract; useful unsolicited findings require independent human evaluation'}
        finally:core.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixture',type=Path,default=Path(__file__).resolve().parents[1]/'examples/intelligence_feed_fixture.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=evaluate(json.loads(args.fixture.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
