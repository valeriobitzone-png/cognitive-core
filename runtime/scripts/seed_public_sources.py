"""Manually verified public-source metadata and a small historical evidence timeline.
All summaries are independently written, not scraped full text.
Citations remain external; no claim of a historical/world-scale corpus.
"""
from __future__ import annotations
import argparse,json
from worldcore import WorldCore

AT='2026-10-30T00:00:00+00:00'
SOURCES=[
 ('Crossref API','https://www.crossref.org/documentation/retrieve-metadata/','Crossref metadata bibliografici; gli abstract possono mantenere diritti degli editori. Importare DOI, titoli e link, non abstract automaticamente.',['science','medicine']),
 ('OpenAlex API','https://help.openalex.org/api/','OpenAlex espone metadati scientifici CC0; l’accesso ha budget e rate limit, con differenze tra utenti autenticati e anonimi.',['science','ai']),
 ('Wikidata CC0','https://www.wikidata.org/wiki/Wikidata:Data_access','Wikidata rende disponibili entità e relazioni strutturate con licenza CC0; per grandi volumi usare dump invece di query pesanti.',['history','geopolitics']),
 ('OpenStreetMap licensing','https://www.openstreetmap.org/copyright','OpenStreetMap fornisce dati geografici con licenza ODbL e obblighi di attribuzione e condivisione a determinate condizioni.',['maps','geospatial']),
 ('World Bank Data Catalog','https://datacatalog.worldbank.org/public-licenses','I dataset World Bank hanno licenze specifiche; CC BY 4.0 è frequente ma non va presunta per ogni raccolta.',['economics','finance']),
 ('PubMed EUtilities','https://support.nlm.nih.gov/kbArticle/?pn=KA-05510','L’API NCBI limita tipicamente le richieste anonime a tre al secondo e consente quote superiori con API key.',['medicine','science']),
 ('GDELT DOC API','https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/','GDELT indicizza articoli internazionali con ricerca nel tempo. Gli articoli restano contenuti editoriali terzi: acquisire soltanto metadati e collegamenti.',['news','geopolitics']),
 ('GitHub REST API limits','https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api','La ricerca repository via API è soggetta a limiti specifici; il motore deve usare cache e backoff ed evitare sincronizzazioni aggressive.',['software','agents']),
 ('Hermes plugin integration','https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/plugins.md','Hermes supporta plugin generali, provider di memoria, context engine e modelli; usare l’interfaccia supportata per integrare WorldCore.',['agents','software']),
 ('OpenClaw plugin hooks','https://github.com/openclaw/openclaw/blob/main/src/plugins/hooks.ts','OpenClaw contiene hook per lifecycle, strumenti e gestione del contesto. L’adattatore va verificato contro la versione host effettiva.',['agents','software']),
 ('Postiz social management','https://github.com/gitroomhq/postiz-app','Postiz supporta schedulazione e analytics social; il repository usa AGPL-3.0, con obblighi specifici per il riuso del codice.',['social_media','marketing']),
 ('OpenSim biomechanics','https://github.com/opensim-org/opensim-core','OpenSim modella strutture muscoloscheletriche per simulazioni scientifiche del movimento; non produce automaticamente prescrizioni cliniche.',['sports_science','medicine']),
]
HISTORY=[
 ('stock_crash_1929','Crollo azionario ottobre 1929','https://www.federalreservehistory.org/essays/stock-market-crash-of-1929',
  'Il Federal Reserve History documenta forti cali del mercato azionario nell’ottobre del 1929; un evento della crisi economica, non una legge predittiva universale.',
  '1929-10-28T00:00:00+00:00',['history','finance'],['United States','NYSE']),
 ('banking_panics_1930','Panico bancario statunitense nel 1930','https://www.federalreservehistory.org/essays/banking-panics-1930-31',
  'La storia della Federal Reserve descrive fallimenti bancari e corse ai prelievi dei depositanti tra il 1930 e 1931; è evidenza storica di una risposta collettiva, non diagnosi di individui.',
  '1930-11-01T00:00:00+00:00',['history','finance','psychology'],['United States','banking']),
 ('great_depression','Grande Depressione','https://www.federalreservehistory.org/essays/great-depression',
  'La Grande Depressione iniziò nel 1929; la ricostruzione della Federal Reserve mette in relazione contrazione economica, crisi bancarie e risposte istituzionali.',
  '1929-08-01T00:00:00+00:00',['history','economics','finance'],['United States']),
 ('berlin_wall_1989','Apertura del Muro di Berlino','https://www.bundesregierung.de/breg-en/service/archive/media-center/the-day-the-berlin-wall-fell-in-november-1989-479456',
  'Il 9 novembre 1989 le notizie sulla nuova libertà di viaggio furono seguite da grandi movimenti di persone verso i valichi; si tratta di cronologia storica verificabile.',
  '1989-11-09T00:00:00+00:00',['history','geopolitics','psychology'],['Berlin','Germany']),
 ('covid_2020','WHO caratterizza COVID-19 come pandemia','https://www.who.int/news-room/speeches/item/who-director-general-s-opening-remarks-at-the-media-briefing-on-covid-19---11-march-2020',
  'L’11 marzo 2020 l’OMS comunicò la valutazione di pandemia per COVID-19. Questo è un evento sanitario e istituzionale documentato.',
  '2020-03-11T00:00:00+00:00',['history','medicine','geopolitics'],['WHO','COVID-19']),
 ('covid_pheic_end_2023','OMS: termina emergenza sanitaria internazionale COVID-19','https://www.who.int/europe/emergencies/situations/covid-19/',
  'Il 5 maggio 2023 l’OMS dichiarò terminata la classificazione come emergenza sanitaria pubblica di rilevanza internazionale; non significa che la malattia sia scomparsa.',
  '2023-05-05T00:00:00+00:00',['history','medicine'],['WHO','COVID-19']),
]
NEWS=[
 ('reuters_crypto_2026_10_29','Reuters: rapporto su incidente di sicurezza Binance','https://www.reuters.com/legal/transactional/tether-circle-freeze-238-billion-after-binance-reports-security-incident-2026-10-29/',
  'Reuters riporta un grave episodio di sicurezza su Binance. Questo record rappresenta una notizia attribuita, non una verifica forense indipendente né un segnale di trading.',
  '2026-10-29T00:00:00+00:00'),
 ('ap_crypto_2026_10_30','AP: Binance indaga su potenziale incidente di sicurezza','https://apnews.com/article/39cda8ceb8095e036334a18549d3d20d',
  'Associated Press riporta le dichiarazioni iniziali relative all’incidente Binance e distingue le somme potenzialmente interessate dalle perdite effettivamente confermate.',
  '2026-10-30T00:00:00+00:00'),
]

def seed(db):
    stats={'sources':0,'history':0,'news_reports':0,'evidence_links':0}
    with WorldCore(db) as core:
        for i,(title,url,summary,topics) in enumerate(SOURCES):
            core.learn_evidence('public_research',{'source':'official_source_guides','record_id':'source_'+str(i),
             'title':title,'summary':summary,'url':url,'license':'METADATA-ONLY','kind':'dataset',
             'published_at':AT,'observed_at':AT,'topics':topics,'entities':[],'confidence':.8},space='source_guides')
            stats['sources']+=1
        for rid,title,url,summary,date,topics,entities in HISTORY:
            core.learn_evidence('public_research',{'source':'official_history','record_id':rid,
              'kind':'event','title':title,'summary':summary,'url':url,'license':'METADATA-ONLY',
              'published_at':date,'observed_at':AT,'topics':topics,'entities':entities,'confidence':.8},space='historical_events')
            stats['history']+=1
        core.link_evidence('public_research',space='historical_events',subject='depositor withdrawals',
              predicate='responds_to',object='bank panic reports',source='official_history',record_id='banking_panics_1930',strength=.7)
        core.link_evidence('public_research',space='historical_events',subject='1929 market crash',
              predicate='precedes',object='1930 bank panics',source='official_history',record_id='banking_panics_1930',strength=.8)
        stats['evidence_links']=2
        for rid,title,url,summary,date in NEWS:
            core.learn_evidence('public_research',{'source':'press_sources','record_id':rid,'kind':'news',
             'title':title,'summary':summary,'url':url,'license':'METADATA-ONLY','published_at':date,
             'observed_at':AT,'topics':['crypto','finance','news','security'],
             'entities':['Binance','Bitcoin'],'confidence':.55},space='news_examples')
            stats['news_reports']+=1
        return stats

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);a=p.parse_args()
    print(json.dumps(seed(a.db),ensure_ascii=False,indent=2))
