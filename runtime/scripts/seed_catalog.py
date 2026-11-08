"""Seed a broad, real GitHub repository catalog with LICENSE UNVERIFIED.
Only public project metadata is indexed, not repository source code.
`readme_checked` means the public README was retrieved, not a code-quality audit.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from worldcore import WorldCore
from worldcore.repo_quality import score_repository

# Each owner/name was successfully read via the connected GitHub tool in this session.
VERIFIED={
 'agents':["NousResearch/hermes-agent","openclaw/openclaw","sailing-lab/sira","Cveinnt/kepler","QwenLM/Qwen-AgentWorld","getzep/graphiti","mem0ai/mem0","langchain-ai/langgraph","letta-ai/letta"],
 'finance':["freqtrade/freqtrade","ccxt/ccxt","polakowo/vectorbt","AI4Finance-Foundation/FinRL","statsmodels/statsmodels"],
 'science':["pandas-dev/pandas","scikit-learn/scikit-learn","pydata/xarray","pytorch/pytorch","biopython/biopython","rdkit/rdkit","openmm/openmm"],
 'medicine':["Project-MONAI/MONAI","mne-tools/mne-python"],
 'psychology':["psychopy/psychopy","simbody/simbody"],
 'sports_science':["opensim-org/opensim-core","pyomeca/pyomeca"],
 'sports_analytics':["PySport/kloppy","hudl/statsbombpy","hudl/open-data"],
 'history':["wikimedia/wikidata-query-rdf"],
 'maps':["QGIS/QGIS","gboeing/osmnx","geopandas/geopandas","organicmaps/organicmaps","Project-OSRM/osrm-backend","valhalla/valhalla"],
 'architecture':["FreeCAD/FreeCAD","IfcOpenShell/IfcOpenShell"],
 '3d_modeling':["blender/blender","mikedh/trimesh","godotengine/godot","alicevision/Meshroom"],
 '3d_printing':["Ultimaker/Cura","prusa3d/PrusaSlicer","bambulab/BambuStudio"],
 'robotics':["ros2/ros2","google-deepmind/mujoco","huggingface/lerobot"],
 'marketing':["n8n-io/n8n","activepieces/activepieces","mautic/mautic","plausible/analytics","matomo-org/matomo","gitroomhq/postiz-app"],
}
FEATURES={
 'NousResearch/hermes-agent':'Agente operativo con strumenti, memoria, hook e provider configurabili',
 'openclaw/openclaw':'Gateway agentico multicanale con plugin, memoria, trigger e automazioni',
 'sailing-lab/sira':'Pianificazione tramite world model, simulazione delle conseguenze e scelta critica',
 'Cveinnt/kepler':'World model verificato contro transizioni reali con controesempi e backtest',
 'QwenLM/Qwen-AgentWorld':'Modello di dinamiche apprese per transizioni in ambienti software',
 'getzep/graphiti':'Grafo di conoscenza temporale per agenti con aggiornamento di relazioni',
 'mem0ai/mem0':'Memoria applicativa personalizzata con acquisizione e recupero di informazioni',
 'langchain-ai/langgraph':'Orchestrazione di stato, checkpoint, iterazioni e workflow agentici',
 'letta-ai/letta':'Agenti persistenti e gestione esplicita delle memorie',
 'freqtrade/freqtrade':'Trading algoritmico crypto, backtesting e gestione delle strategie',
 'ccxt/ccxt':'Interfacce multi-exchange per dati e ordini di criptovalute',
 'polakowo/vectorbt':'Ricerca quantitativa e backtesting vettorializzato',
 'AI4Finance-Foundation/FinRL':'Reinforcement learning applicato a simulazioni di trading',
 'statsmodels/statsmodels':'Inferenza statistica e serie temporali econometriche',
 'pandas-dev/pandas':'Trasformazione e validazione di dati tabellari e temporali',
 'scikit-learn/scikit-learn':'Modelli supervisionati classici, pipeline e valutazione',
 'pydata/xarray':'Strutture dati multidimensionali etichettate per scienza e clima',
 'pytorch/pytorch':'Calcolo tensoriale e apprendimento automatico differenziabile',
 'biopython/biopython':'Bioinformatica e rappresentazione di dati biologici',
 'rdkit/rdkit':'Cheminformatica e rappresentazione di strutture molecolari',
 'openmm/openmm':'Simulazione numerica molecolare',
 'Project-MONAI/MONAI':'Framework di ricerca per imaging medico; non è un dispositivo diagnostico',
 'mne-tools/mne-python':'Analisi scientifica di segnali EEG e MEG',
 'psychopy/psychopy':'Progettazione e misurazione di esperimenti comportamentali',
 'simbody/simbody':'Simulazione dei sistemi multibody articolati',
 'opensim-org/opensim-core':'Biomeccanica muscoloscheletrica e simulazione del movimento',
 'pyomeca/pyomeca':'Analisi scientifica di dati biomeccanici e cinetici',
 'PySport/kloppy':'Normalizzazione di dati eventi e tracking calcistici tra fornitori',
 'hudl/statsbombpy':'Accesso e elaborazione dei dati calcistici StatsBomb',
 'hudl/open-data':'Dataset pubblici di eventi calcistici con propri termini di utilizzo',
 'wikimedia/wikidata-query-rdf':'Accesso a knowledge graph RDF e query SPARQL Wikidata',
 'QGIS/QGIS':'GIS desktop e strumenti di analisi cartografica',
 'gboeing/osmnx':'Reti stradali OpenStreetMap e analisi di grafi spaziali',
 'geopandas/geopandas':'Analisi di geometrie spaziali e tabelle geografiche',
 'organicmaps/organicmaps':'Mappe e navigazione offline',
 'Project-OSRM/osrm-backend':'Routing stradale ad alte prestazioni',
 'valhalla/valhalla':'Motore open source per il calcolo di itinerari',
 'FreeCAD/FreeCAD':'Modellazione CAD parametrica e produzione tecnica',
 'IfcOpenShell/IfcOpenShell':'Lettura, generazione e gestione di dati BIM IFC',
 'blender/blender':'Modellazione, animazione, rendering e pipeline 3D',
 'mikedh/trimesh':'Analisi e trasformazione geometrica delle mesh 3D',
 'godotengine/godot':'Motore per mondi interattivi, simulazioni e videogiochi',
 'alicevision/Meshroom':'Ricostruzione tridimensionale da fotografie',
 'Ultimaker/Cura':'Slicing e preparazione dei lavori per stampa 3D',
 'prusa3d/PrusaSlicer':'Preparazione G-code e slicing per stampa FDM',
 'bambulab/BambuStudio':'Slicer e workflow di stampa 3D Bambu',
 'ros2/ros2':'Middleware e interoperabilità dei sistemi robotici',
 'google-deepmind/mujoco':'Simulazione di dinamiche fisiche e robotica',
 'huggingface/lerobot':'Dati, modelli e workflow di apprendimento robotico',
 'n8n-io/n8n':'Automazione di workflow e integrazione di sistemi esterni',
 'activepieces/activepieces':'Automazione self-hosted con connettori applicativi',
 'mautic/mautic':'Gestione di campagne e automazioni di marketing',
 'plausible/analytics':'Analisi web orientata alla privacy',
 'matomo-org/matomo':'Web analytics e misurazione delle campagne',
 'gitroomhq/postiz-app':'Programmazione editoriale, pubblicazione e analytics social'
}
SUPPLEMENTARY={
 'history':[('wikidata','https://www.wikidata.org/wiki/Wikidata:Data_access','CC0 historical entity/event metadata')],
 'news':[('GDELT DOC','https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/','News index metadata/links; article copyrights not transferred')],
 'science':[('OpenAlex','https://help.openalex.org/api/','CC0 work metadata'),('Crossref','https://www.crossref.org/documentation/retrieve-metadata/','Metadata broadly reusable; abstracts excluded')],
 'medicine':[('NCBI E-utilities','https://www.ncbi.nlm.nih.gov/books/NBK25501/','PubMed bibliographic records; individual abstracts may be restricted')],
 'economics':[('World Bank Data','https://datacatalog.worldbank.org/public-licenses','Per-dataset licenses must be checked')],
 'geospatial':[('OpenStreetMap','https://www.openstreetmap.org/copyright','ODbL; database and attribution conditions')],
}


def seed(db:str,owner='public_research',space='repo_catalog'):
    at='2026-10-30T00:00:00+00:00'
    stats={'verified_readme':0,'updated':0,'unchanged':0}
    with WorldCore(db) as core:
        for topic,repos in VERIFIED.items():
            for name in repos:
                slug=name.replace('/','__')
                rec={'source':'github_curated','record_id':'repo_'+slug,'kind':'repo',
                   'title':name,'summary':f'Capacità documentata: {FEATURES[name]}. Repo GitHub con README consultato il 30 ottobre 2026. Qualità del codice, test e condizioni di riuso da verificare prima dell’integrazione.',
                   'url':'https://github.com/'+name,'license':'METADATA-ONLY',
                   'published_at':at,'observed_at':at,
                   'topics':([topic,'software','crypto'] if name in ('freqtrade/freqtrade','ccxt/ccxt') else [topic,'software','social_media'] if name=='gitroomhq/postiz-app' else [topic,'software'] if topic!='software' else ['software']),
                   'entities':[name],'confidence':0.5}
                status=core.learn_evidence(owner,rec,space=space)['status']
                stats['verified_readme']+=1
                stats[status]=stats.get(status,0)+1
        result=core.intelligence_stats(owner,space=space)
    return {'catalog':result,'seed':stats,'source_registry':SUPPLEMENTARY,
      'quality_gate':score_repository({'docs':True}),
      'important':'README presence is NOT a code audit; no full repository code was imported'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--owner',default='public_research')
    p.add_argument('--space',default='repo_catalog');a=p.parse_args()
    print(json.dumps(seed(a.db,a.owner,a.space),indent=2,ensure_ascii=False))

if __name__=='__main__':main()
