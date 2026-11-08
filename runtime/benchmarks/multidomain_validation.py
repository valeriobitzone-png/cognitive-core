"""Reproducible smoke test of multi-domain retrieval. Labels are author-defined,
not blinded external QA; the goal is evidence retrieval, NOT natural language reasoning.
"""
from __future__ import annotations
from pathlib import Path
from time import perf_counter
from statistics import median
import argparse,json
from worldcore import WorldCore

CASES=[
 ('repo_catalog','modello mondo simulazione ragionamento',['sailing-lab/sira','QwenLM/Qwen-AgentWorld']),
 ('repo_catalog','backtesting trading criptovalute',['freqtrade/freqtrade','polakowo/vectorbt']),
 ('repo_catalog','interfaccia exchange bitcoin crypto',['ccxt/ccxt']),
 ('repo_catalog','deep learning tensoriale',['pytorch/pytorch']),
 ('repo_catalog','statistica serie temporali',['statsmodels/statsmodels']),
 ('repo_catalog','imaging medico',['Project-MONAI/MONAI']),
 ('repo_catalog','esperimenti comportamentali',['psychopy/psychopy']),
 ('repo_catalog','simulazione del movimento muscoloscheletrico',['opensim-org/opensim-core']),
 ('repo_catalog','tracking calcistico',['PySport/kloppy']),
 ('repo_catalog','grafo della conoscenza Wikidata RDF',['wikimedia/wikidata-query-rdf']),
 ('repo_catalog','GIS mappe geografiche',['QGIS/QGIS']),
 ('repo_catalog','routing itinerari stradali',['Project-OSRM/osrm-backend','valhalla/valhalla']),
 ('repo_catalog','BIM IFC architettura',['IfcOpenShell/IfcOpenShell']),
 ('repo_catalog','CAD parametrica',['FreeCAD/FreeCAD']),
 ('repo_catalog','modellazione mesh animazione 3D',['blender/blender','mikedh/trimesh']),
 ('repo_catalog','slicing stampa 3D',['prusa3d/PrusaSlicer','bambulab/BambuStudio','Ultimaker/Cura']),
 ('repo_catalog','robotica reinforcement learning',['huggingface/lerobot','ros2/ros2']),
 ('repo_catalog','social editoriale pubblicazione analytics',['gitroomhq/postiz-app']),
 ('repo_catalog','web analytics privacy',['plausible/analytics','matomo-org/matomo']),
 ('historical_events','banche depositanti corse prelievi',['Panico bancario statunitense nel 1930']),
 ('historical_events','pandemia OMS',['WHO caratterizza COVID-19 come pandemia']),
 ('source_guides','licenza mappe OpenStreetMap ODbL',['OpenStreetMap licensing']),
]

def evaluate(db):
    scores=[];times=[]
    with WorldCore(db) as c:
        for space,q,expected in CASES:
            t=perf_counter()
            r=c.query_intelligence('public_research',q,space=space,limit=5)
            times.append((perf_counter()-t)*1000)
            scores.append({'space':space,'query':q,'expected':expected,
                           'retrieved':[x['title'] for x in r[:5]],
                           'hit_at_5':bool(set(expected)&{x['title'] for x in r[:5]})})
        return {'cases':len(scores),'hit_at_5':sum(x['hit_at_5'] for x in scores),
                'recall_at_5':sum(x['hit_at_5'] for x in scores)/len(scores),
                'median_search_ms':round(median(times),3),
                'scope_counts':{s:c.intelligence_stats('public_research',space=s)['records']
                    for s in ['repo_catalog','source_guides','historical_events','news_examples']},
                'label_warning':'Queries and expected targets are author-prepared; smoke test, not blinded semantic QA or trained intelligence',
                'queries':scores}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    result=evaluate(a.db)
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(f"Author-labelled retrieval: {result['hit_at_5']}/{result['cases']}, median {result['median_search_ms']} ms")
