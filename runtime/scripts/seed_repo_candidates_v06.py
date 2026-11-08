"""Import GitHub candidate metadata only. Never implies code was trained or audited."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from worldcore import WorldCore

TOPICS={
 'world_models':['ai','agents'],'agents':['agents','ai'],'mcp_api':['agents','software'],
 'finance_crypto':['finance','crypto'],'news_history':['news','history'],
 'psychology_neuro':['psychology','science'],
 'medicine_biology':['medicine','biology'],'sports':['sports_science','sports_analytics'],
 'maps_geospatial':['maps','geospatial'],'architecture_bim':['architecture','bim'],
 '3d_printing':['3d_printing','3d_modeling'],'vision_robotics':['robotics','ai'],
 'social_marketing':['social_media','marketing'],
 'llm_nlp':['ai','software'],'ai_eval_security':['ai','security'],
 'causal_science':['science','ai'],
 'finance':['finance'],'3d_modeling':['3d_modeling'],'architecture':['architecture'],
 'maps':['maps'],'marketing':['marketing'],'sports_science':['sports_science'],
 'sports_analytics':['sports_analytics'],'history':['history'],
 'psychology':['psychology'],'medicine':['medicine'],'science':['science'],
 'robotics':['robotics'],
}

def seed(db_path):
    records=json.loads((ROOT/'catalog/repository_candidates_v06.json').read_text())
    added,unchanged=0,0
    with WorldCore(db_path) as w:
        for item in records:
            tier=item['selection_tier']
            summary=(item['original_capability_summary']+'; '+
                     ('README examined; code/security/license not audited' if tier=='README_EXAMINED' else
                      'GitHub search discovery only; not audited or trained')+'.')
            rid='repo_'+hashlib.sha256(item['repo'].encode()).hexdigest()[:20]
            res=w.learn_evidence('public_research',{
                'source':'github_candidate_v06','record_id':rid,'kind':'repo',
                'title':item['repo'],'summary':summary[:1200],
                'url':item['url'],'license':'METADATA-ONLY','published_at':'2026-10-30T06:00:00+00:00',
                'topics':TOPICS.get(item['domain'],['other']),
                'confidence':0.55 if tier=='README_EXAMINED' else 0.25,
                'entities':[item['repo']],
            },space='repo_candidates')
            added+=res['status']=='added';unchanged+=res['status']=='unchanged'
        integrity=w.db.execute('PRAGMA integrity_check').fetchone()[0]
        count=w.db.execute("SELECT count(*) FROM intel_current WHERE owner='public_research' AND space='repo_candidates'").fetchone()[0]
    return {'added':added,'unchanged':unchanged,'total':count,'db_integrity':integrity}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True)
    print(json.dumps(seed(p.parse_args().db),indent=2))
