"""Explicit one-shot metadata-only public API refresh, OFF by default.

No full-text articles, code cloning or auto-training LLM. Never schedule as a
background job without owner consent and an external scheduler.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from worldcore import WorldCore
from worldcore.feeds import import_feed

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError('redirect disallowed for public data connector')

HOSTS={'crossref':'api.crossref.org','openalex':'api.openalex.org',
       'gdelt':'api.gdeltproject.org','github':'api.github.com'}


def url_for(provider,topic,count):
    if provider=='crossref':path='/works'; q={'query':topic,'rows':count,'select':'DOI,title,published,created'}
    elif provider=='openalex':path='/works';q={'search':topic,'per_page':count,'select':'id,display_name,publication_date'}
    elif provider=='gdelt':path='/api/v2/doc/doc';q={'query':topic,'mode':'ArtList','format':'json','maxrecords':count,'timespan':'1d'}
    elif provider=='github':path='/search/repositories';q={'q':topic,'per_page':count}
    else:raise ValueError('unsupported provider')
    return f'https://{HOSTS[provider]}{path}?{urlencode(q)}'


def safe_fetch(url,max_bytes=1_000_000):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in HOSTS.values() or p.port not in (None,443) or p.username:
        raise ValueError('URL not in fixed public-API allowlist')
    req=Request(url,headers={'User-Agent':'WorldCoreResearch/0.5 (metadata only; manual opt-in)',
                             'Accept':'application/json'})
    with build_opener(NoRedirect).open(req,timeout=12) as res:
        size=res.headers.get('Content-Length')
        if size and int(size)>max_bytes:raise ValueError('response too large')
        data=res.read(max_bytes+1)
    if len(data)>max_bytes:raise ValueError('response too large')
    return json.loads(data.decode('utf-8'))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--provider',choices=sorted(HOSTS),required=True)
    p.add_argument('--topic',required=True,help='Topic such as ai, medicine, 3d_printing')
    p.add_argument('--db',required=True);p.add_argument('--owner',default='public_research')
    p.add_argument('--space',default='daily_evidence');p.add_argument('--max-items',type=int,default=30)
    p.add_argument('--fixture',type=Path,help='Load stored JSON; network disabled')
    p.add_argument('--allow-network',action='store_true',help='Explicit operator-approved live fetch')
    a=p.parse_args()
    if not 1<=a.max_items<=50:p.error('max-items must be 1..50')
    if a.fixture:
        payload=json.loads(a.fixture.read_text(encoding='utf-8'))
        method='offline fixture'
    elif a.allow_network:
        url=url_for(a.provider,a.topic,a.max_items)
        payload=safe_fetch(url)
        method='live request from allowlisted API'
    else:
        p.error('external fetch disabled: use --fixture FILE or explicitly --allow-network')
    with WorldCore(a.db) as core:
        report=import_feed(core,a.owner,a.provider,payload,topic=a.topic,space=a.space,max_items=a.max_items)
    report['method']=method;print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
