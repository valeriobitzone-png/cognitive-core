import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cognitive_core.config import Settings
from cognitive_core.engine import CognitiveCore
from cognitive_core.decision import Reflex,DecisionPlane,LocalDecisionModel
from cognitive_core.research import PageParser,assert_public_https
from cognitive_core.world import WorldModel
from cognitive_core.learn import add_reviewed_example,export_supervised_jsonl
from cognitive_core.obsidian import ingest_markdown_tree


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.s=Settings(home=Path(self.tmp.name))
        self.c=CognitiveCore(self.s)

    def tearDown(self):
        self.c.close();self.tmp.cleanup()

    def test_greeting_zero_db_and_zero_model(self):
        d=self.c.observe({'kind':'message','text':'Ciao!'})
        self.assertEqual(d['action'],'WAIT')
        self.assertFalse(self.s.db_path.exists())

    def test_trivial_greetings_multilingual(self):
        for v in ['ciao',' Hello! ','salve','OK','grazie','hi']:
            self.assertEqual(self.c.observe({'text':v})['action'],'WAIT')
        self.assertFalse(self.s.db_path.exists())

    def test_session_to_jobs(self):
        out=self.c.observe({'kind':'session_end','title':'3D project','open_questions':[
              'How does PLA humidity impact printing?', 'Which nozzle size is appropriate?']})
        self.assertEqual(len(out['topics']),2)
        self.assertEqual(len(self.c.vault.pending_jobs()),2)
        self.assertTrue(out['stored'])

    def test_research_blocked_by_default(self):
        self.c.observe({'kind':'question_open','question':'Explore a missing specification'})
        res=self.c.work_once()
        self.assertEqual(res['status'],'blocked')
        self.assertEqual(self.c.vault.usage('web_requests'),0)

    def test_discard_cancels(self):
        out=self.c.observe({'kind':'question_open','question':'Do not continue this discarded idea'})
        topic=out['topics'][0]
        self.c.vault.set_topic_status(topic,'discarded')
        self.assertEqual(self.c.vault.pending_jobs(),[])
        with self.assertRaises(PermissionError):self.c.resume(topic)

    def test_paused_is_not_leased(self):
        out=self.c.observe({'kind':'question_open','question':'Research printer specifications', 'paused':True})
        self.assertEqual(len(self.c.vault.pending_jobs()),0)
        self.c.resume(out['topics'][0])
        self.assertEqual(len(self.c.vault.pending_jobs()),1)

    def test_claims_never_become_tested_on_link(self):
        t=self.c.vault.topic('T','What should be true?')
        doc1=self.c.vault.document('Doc','Source content','https://example.org/1')
        doc2=self.c.vault.document('Doc2','Other source','https://example.org/2')
        claim=self.c.vault.claim(t,'A claim')
        self.c.vault.add_evidence(claim,doc1,'Source text','supports')
        r=self.c.vault.db.execute('SELECT status FROM claims WHERE id=?',(claim,)).fetchone()
        self.assertEqual(r['status'],'source_backed')
        self.c.vault.add_evidence(claim,doc2,'Contrary text','contradicts')
        r=self.c.vault.db.execute('SELECT status FROM claims WHERE id=?',(claim,)).fetchone()
        self.assertEqual(r['status'],'conflicted')

    def test_predictions_scored_against_outcomes(self):
        t=self.c.vault.topic('Prediction','Will the event occur?')
        p=self.c.vault.predict(t,'This event will occur',.75,'tomorrow')
        self.assertAlmostEqual(self.c.vault.resolve_prediction(p,False),.5625)
        with self.assertRaises(ValueError):self.c.vault.resolve_prediction(p,False)

    def test_hypothetical_branches_do_not_mutate_world(self):
        state={'filament':'PLA'}
        output=WorldModel().compare(state,[{'name':'a','changes':{'filament':'PETG'},'value':.8,'permitted':True},
                                         {'name':'b','changes':{'filament':'ABS'},'value':.9,'permitted':False}])
        self.assertEqual(state['filament'],'PLA')
        self.assertEqual(output[0]['name'],'a')
        self.assertEqual(output[1]['score'],float('-inf'))

    def test_atomic_budget(self):
        self.assertTrue(self.c.vault.reserve_budget('web_requests',2))
        self.assertTrue(self.c.vault.reserve_budget('web_requests',2))
        self.assertFalse(self.c.vault.reserve_budget('web_requests',2))
        self.assertEqual(self.c.vault.usage('web_requests'),2)

    def test_web_access_denied_no_explicit_permission(self):
        from cognitive_core.research import Researcher
        with self.assertRaises(PermissionError):Researcher(self.s).fetch('https://www.example.org')

    def test_web_local_ip_and_http_denied(self):
        with self.assertRaises(ValueError):assert_public_https('http://example.com',['example.com'])
        with self.assertRaises(ValueError):assert_public_https('https://127.0.0.1/test',['127.0.0.1'])
        with self.assertRaises(ValueError):assert_public_https('https://www.example.com',['other.org'])

    def test_vision_model_requires_loopback(self):
        bad=Settings(home=Path(self.tmp.name),local_model_url='https://api.openai.com/v1/chat/completions')
        with self.assertRaises(ValueError):LocalDecisionModel(bad)

    def test_web_parser_returns_image_metadata_not_fake_vision(self):
        page=PageParser()
        page.feed('<html><head><title>3D Print</title><style>secret</style></head><body><h1>Material</h1><img src="/photo.png" alt="Printer"><script>malicious()</script></body></html>')
        d=page.result('https://example.org/article')
        self.assertEqual(d['images'][0]['url'],'https://example.org/photo.png')
        self.assertNotIn('malicious()',d['text'])
        self.assertEqual(d['title'],'3D Print')

    def test_search_and_export(self):
        self.c.vault.document('PLA manual','Filament temperature details','https://example.org/manual')
        self.assertEqual(len(self.c.memory_search('temperature')),1)
        target=Path(self.tmp.name)/'export'
        count=self.c.vault.export_markdown(target)
        self.assertEqual(count,1)
        self.assertEqual(len(list(target.glob('doc_*.md'))),1)
        self.assertTrue((target/'claims.json').exists())

    def test_workspace_namespace_isolated(self):
        self.c.vault.document('Secret','The confidential elephant says hello')
        other=CognitiveCore(Settings(home=Path(self.tmp.name),namespace='other'))
        try:self.assertEqual(other.memory_search('elephant'),[])
        finally:other.close()

    def test_bounded_worker_mock_research_and_checkpoint(self):
        self.c.close()
        self.s=Settings(home=Path(self.tmp.name),enable_web=True,domain_allowlist=('example.org',),
                        max_web_requests_per_day=2,max_web_requests_per_job=2)
        self.c=CognitiveCore(self.s)
        self.c.observe({'kind':'research_requested','question':'Research external documentation',
                        'seed_urls':['https://example.org/a','https://example.org/b']})
        page={'title':'Technical note','text':'Test material description','url':'https://example.org/a',
              'content_type':'text/html','images':[{'url':'https://example.org/img.png','alt':'diagram'}]}
        with patch('cognitive_core.engine.Researcher.fetch',return_value=page):
            res=self.c.work_once()
        self.assertEqual(res['status'],'done')
        self.assertEqual(res['verified_claims'],0)
        self.assertEqual(self.c.vault.usage('web_requests'),2)
        self.assertEqual(self.c.vault.usage('jobs_run'),1)
        self.assertEqual(self.c.vault.get_job(res['job_id'])['status'],'done')
        self.assertEqual(res['images_discovered'],1)
        self.assertEqual(len(res['sources']),1) # same content + URL deduplicated; visits still checkpointed

    def test_leased_crashed_job_can_resume(self):
        x=self.c.observe({'kind':'question_open','question':'Learn a new tool in another session'})
        lease=self.c.vault.lease_job()
        self.c.vault.db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(lease['id'],))
        again=self.c.vault.lease_job()
        self.assertEqual(again['id'],lease['id'])
        self.assertEqual(again['attempts'],2)

    def test_reviewed_learning_examples(self):
        path=Path(self.tmp.name)/'train'
        with self.assertRaises(ValueError):add_reviewed_example(path,event={'text':'ciao'},label='WAIT',rationale='greeting',reviewed_by='')
        add_reviewed_example(path,event={'text':'ciao'},label='WAIT',rationale='greeting',reviewed_by='reviewer')
        self.assertEqual(export_supervised_jsonl(path,Path(self.tmp.name)/'train.jsonl'),1)

    def test_markdown_import(self):
        d=Path(self.tmp.name)/'notes';d.mkdir()
        (d/'spec.md').write_text('# Printer filament specification',encoding='utf-8')
        out=ingest_markdown_tree(self.c.vault,d)
        self.assertEqual(out['indexed'],1)
        self.assertEqual(len(self.c.memory_search('filament')),1)

    def test_reflex_external_action_requires_approval(self):
        x=self.c.observe({'kind':'external_action','text':'spend money'})
        self.assertFalse(x['approved'])
        self.assertFalse(x['stored'])

    def test_paid_calls_cannot_be_enabled(self):
        with self.assertRaises(ValueError):Settings(external_paid_calls_allowed=True)


if __name__=='__main__':unittest.main()
