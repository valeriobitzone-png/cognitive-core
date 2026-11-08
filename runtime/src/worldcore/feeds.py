"""Offline-testable adapters for public structured metadata (not article/copyright full text).

The adapters accept already-fetched JSON; network is *never* invoked implicitly.
Provider terms, rate limits and rights must be checked before enabling a fetcher.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
import json
import re
from .intelligence import DOMAINS


def _rid(prefix,text):
    # Content-derived id avoids unsafe characters in external provider IDs.
    return prefix+'_'+sha256(str(text).encode()).hexdigest()[:24]


def _time(ts):
    if not isinstance(ts,str) or not ts.strip():return datetime.now(timezone.utc).isoformat()
    val=ts.strip()
    if re.fullmatch(r'\d{8}T\d{6}Z',val):
        return datetime.strptime(val,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).isoformat()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',val):return val+'T00:00:00+00:00'
    if val.endswith('Z'):val=val[:-1]+'+00:00'
    d=datetime.fromisoformat(val)
    return d.replace(tzinfo=timezone.utc).isoformat() if d.tzinfo is None else d.astimezone(timezone.utc).isoformat()


def _summary(label,source,extra=''):
    # Never copy an abstract, news article or license-unclear raw text.
    return f'Metadato bibliografico o notizia indicizzata da {source}. {label}. {extra}'.strip()[:700]


def normalize_feed(provider:str,payload:dict,*,topic:str,observed_at:str|None=None,max_items:int=100):
    """Convert selected public metadata into bounded, attributed records.

    Not a web crawler. This does not assert the underlying article is true.
    """
    if topic not in DOMAINS:raise ValueError('unknown topic')
    if not isinstance(payload,dict) or not 1<=max_items<=200:raise ValueError('invalid feed or max_items')
    observed=_time(observed_at) if observed_at else datetime.now(timezone.utc).isoformat()
    records=[]
    if provider=='crossref':
        items=payload.get('message',{}).get('items',[])
        for x in items[:max_items]:
            doi=x.get('DOI'); titles=x.get('title',[])
            if not doi or not titles:continue
            title=str(titles[0])[:200];url='https://doi.org/'+str(doi)
            published=x.get('published',x.get('created',{}))
            parts=published.get('date-parts',[]) if isinstance(published,dict) else []
            date= '-'.join(str(i).zfill(2) if j else str(i) for j,i in enumerate(parts[0])) if parts else None
            if date and len(date)==4:date+='-01-01'
            if date and len(date)==7:date+='-01'
            pub=_time(date) if date else observed
            records.append({'source':'crossref','record_id':_rid('doi',doi),'kind':'research',
             'title':title,'summary':_summary(title,'Crossref',f'DOI: {doi}'),
             'url':url,'license':'METADATA-ONLY','published_at':min(pub,observed),'observed_at':observed,
             'topics':[topic],'entities':[],'confidence':0.6})
    elif provider=='openalex':
        for x in payload.get('results',[])[:max_items]:
            wid=x.get('id');title=x.get('display_name');date=x.get('publication_date')
            if not wid or not title or not str(wid).startswith('https://openalex.org/'):continue
            records.append({'source':'openalex','record_id':_rid('work',wid),'kind':'research',
              'title':str(title)[:200],'summary':_summary(str(title)[:180],'OpenAlex',f'Work ID: {wid}'),
              'url':wid,'license':'CC0','published_at':min(_time(date) if date else observed,observed),
              'observed_at':observed,'topics':[topic],'entities':[],'confidence':0.65})
    elif provider=='gdelt':
        for x in payload.get('articles',[])[:max_items]:
            url=x.get('url');title=x.get('title');t=x.get('seendate')
            if not isinstance(url,str) or not url.startswith('https://') or not title:continue
            records.append({'source':'gdelt','record_id':_rid('article',url),'kind':'news','title':str(title)[:200],
             'summary':f'GDELT ha indicizzato un articolo con questo titolo: {str(title)[:160]}. Titolo non verificato in modo indipendente.',
             'url':url,'license':'METADATA-ONLY','published_at':min(_time(t) if t else observed,observed),
             'observed_at':observed,'topics':[topic],'entities':[],'confidence':0.35})
    elif provider=='wikidata':
        # SPARQL JSON response for a bounded historical-event query. This stores
        # Wikidata assertions as ATTRIBUTED metadata, not established causality.
        bindings=payload.get('results',{}).get('bindings',[])
        for x in bindings[:max_items]:
            item=x.get('item',{}).get('value','')
            label=x.get('itemLabel',{}).get('value','')
            date=x.get('date',{}).get('value','')
            if not item.startswith('http://www.wikidata.org/entity/Q') and not item.startswith('https://www.wikidata.org/entity/Q'):
                continue
            if not label or not date:continue
            url=item.replace('http://','https://')
            pub=min(_time(date),observed)
            records.append({'source':'wikidata','record_id':_rid('entity',item),'kind':'event',
              'title':str(label)[:200],
              'summary':f'Wikidata riporta un evento o entità denominato {str(label)[:150]} associato alla data {date[:25]}. La data e le relazioni necessitano di verifica della fonte.',
              'url':url,'license':'CC0','published_at':pub,'observed_at':observed,
              'topics':[topic],'entities':[str(label)[:90]],'confidence':0.45})
    elif provider=='worldbank':
        # Adapter for manually extracted World Bank indicator observations.
        # Rights are metadata-only pending per-dataset license validation.
        for x in payload.get('observations',[])[:max_items]:
            code=str(x.get('indicator',''))[:55];country=str(x.get('country',''))[:60]
            year=str(x.get('year',''));value=x.get('value')
            if not code or not country or not re.fullmatch(r'\d{4}',year) or not isinstance(value,(float,int)) or isinstance(value,bool):continue
            try:
                val=float(value)
                if not (float('-inf')<val<float('inf')):continue
            except (ValueError,TypeError):continue
            desc=f'Indicatore World Bank {code}, territorio {country}, anno {year}, valore numerico {val:.6g}. Unità e serie vanno controllate nel catalogo.'
            records.append({'source':'worldbank','record_id':_rid('series',code+country+year),
              'kind':'observation','title':f'{code} — {country} ({year})',
              'summary':desc,'url':'https://data.worldbank.org/indicator/'+code,
              'license':'METADATA-ONLY','published_at':min(_time(year+'-01-01'),observed),
              'observed_at':observed,'topics':[topic],'entities':[country], 'confidence':0.55})
    elif provider=='github':
        for x in payload.get('items',[])[:max_items]:
            name,url=x.get('full_name'),x.get('html_url')
            if not name or not isinstance(url,str) or not url.startswith('https://github.com/'):continue
            description=x.get('description') or 'Repository di software pubblico; verificare README, codice, licenza e manutenzione.'
            records.append({'source':'github','record_id':_rid('repo',name),'kind':'repo','title':name,
              'summary':_summary(str(description)[:450],'GitHub', 'Metadati, non verifica di qualità.'),
              'url':url,'license':'METADATA-ONLY','published_at':min(_time(x.get('pushed_at') or observed),observed),
              'observed_at':observed,'topics':[topic,'software'] if topic!='software' else ['software'],
              'entities':[],'confidence':0.4})
    else:raise ValueError('unsupported provider')
    return records


def import_feed(core,owner,provider,payload,*,topic,space='default',observed_at=None,max_items=100):
    """Explicit import; no scheduler, no auto-network, no self-promotion to facts."""
    rows=normalize_feed(provider,payload,topic=topic,observed_at=observed_at,max_items=max_items)
    results={'added':0,'updated':0,'unchanged':0,'rejected':0,'examples':[]}
    for row in rows:
        try:
            r=core.learn_evidence(owner,row,space=space)
            results[r['status']]+=1
        except (ValueError,TypeError) as e:
            results['rejected']+=1
            if len(results['examples'])<5:results['examples'].append(str(e))
    results['provider']=provider;results['processed']=len(rows)
    return results
