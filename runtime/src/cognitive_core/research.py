"""Opt-in web source reader. Network disabled unless explicitly configured.

Production network hardening and content licencing review remain required.
"""
import html
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
import http.client
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from urllib.error import URLError
from .config import Settings


class BudgetExceeded(PermissionError):
    pass


class PublicHTTPSConnection(http.client.HTTPSConnection):
    """Connect to the validated address, retaining TLS verification for the host."""
    def connect(self):
        if self._tunnel_host:raise PermissionError('proxy tunnels are disabled')
        addresses=socket.getaddrinfo(self.host,self.port,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise PermissionError('non-public resolved address')
        sock=socket.create_connection((addresses[0][4][0],self.port),self.timeout)
        try:
            self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


class PublicHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self,req):
        return self.do_open(PublicHTTPSConnection,req,context=self._context)


def read_bounded(response,limit,timeout):
    deadline=time.monotonic()+timeout
    chunks=[];size=0
    while size<=limit:
        if time.monotonic()>=deadline:raise TimeoutError('response deadline exceeded')
        chunk=response.read1(min(65536,limit+1-size))
        if not chunk:break
        chunks.append(chunk);size+=len(chunk)
    if size>limit:raise ValueError('response too large')
    return b''.join(chunks)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.images=[]
        self.title=[]
        self.in_title=False
        self.skip=0

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript'):
            self.skip+=1
        if tag=='title':
            self.in_title=True
        if tag=='img':
            self.images.append({'src':attrs.get('src',''), 'alt':attrs.get('alt','')[:350]})

    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):
            self.skip=max(0,self.skip-1)
        if tag=='title':
            self.in_title=False

    def handle_data(self,data):
        if self.in_title:
            self.title.append(data)
        if self.skip==0 and data.strip():
            self.parts.append(data.strip())

    def result(self,base_url):
        text=re.sub(r'\s+',' ',' '.join(self.parts))
        return {'title':' '.join(self.title).strip() or base_url,
                'text':text,'images':[{'url':urllib.parse.urljoin(base_url,i['src']),
                                      'alt':i['alt']} for i in self.images if i['src']][:100]}


def _domain_allowed(host, allowlist):
    return any(host==d or host.endswith('.'+d) for d in allowlist)


def assert_public_https(url, allowlist):
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password:
        raise ValueError('web access restricted to HTTPS URLs')
    if u.port not in (None,443):
        raise ValueError('nonstandard web port denied')
    if not allowlist or not _domain_allowed(u.hostname.lower(), allowlist):
        raise ValueError('domain is not explicitly allowlisted')
    for item in socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM):
        address=ipaddress.ip_address(item[4][0])
        if not address.is_global:
            raise ValueError('private or non-global network destination denied')
    return u


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise PermissionError('redirects require an explicit new source URL')


class Researcher:
    def __init__(self,s: Settings,reserve_additional_request=None):
        self.s=s
        self.reserve_additional_request=reserve_additional_request

    def fetch(self,url):
        if not self.s.enable_web:
            raise PermissionError('network disabled')
        assert_public_https(url,self.s.domain_allowlist)
        # robots.txt should be respected. Network or parsing error = refuse.
        parsed=urllib.parse.urlsplit(url)
        robots=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,'/robots.txt','',''))
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),PublicHTTPSHandler(),NoRedirect())
        r=urllib.robotparser.RobotFileParser()
        r.set_url(robots)
        try:
            robots_request=urllib.request.Request(robots,headers={'User-Agent':'CognitiveCoreResearch/0.1'})
            with opener.open(robots_request,timeout=self.s.request_timeout_seconds) as robots_response:
                robots_text=read_bounded(robots_response,100_000,self.s.request_timeout_seconds).decode('utf-8',errors='replace')
            r.parse(robots_text.splitlines())
        except Exception as exc:
            raise PermissionError(f'cannot verify robots.txt: {type(exc).__name__}')
        if not r.can_fetch('CognitiveCoreResearch/0.1',url):
            raise PermissionError('robots policy denies research')
        if self.reserve_additional_request:self.reserve_additional_request()
        req=urllib.request.Request(url,headers={'User-Agent':'CognitiveCoreResearch/0.1 (local, opt-in)','Accept':'text/html,text/plain,application/json'})
        with opener.open(req,timeout=self.s.request_timeout_seconds) as response:
            if response.geturl()!=url:
                assert_public_https(response.geturl(),self.s.domain_allowlist)
            content_type=response.headers.get_content_type()
            if content_type not in ('text/html','text/plain','application/json'):
                raise ValueError(f'unsupported content type {content_type}; configure a document extractor')
            data=read_bounded(response,self.s.max_text_bytes,self.s.request_timeout_seconds)
            charset=response.headers.get_content_charset() or 'utf-8'
            raw=data.decode(charset,errors='replace')
            if content_type=='text/html':
                parser=PageParser();parser.feed(raw)
                parsed_page=parser.result(response.geturl())
            else:
                parsed_page={'title':response.geturl(),'text':raw,'images':[]}
            parsed_page['url']=response.geturl()
            parsed_page['content_type']=content_type
            parsed_page['untrusted']=True
            return parsed_page

    def search(self, query, limit=5):
        """SearXNG JSON, explicit opt-in. No automatic paid APIs."""
        if not self.s.enable_web or not self.s.searxng_url:
            raise PermissionError('search requires opt-in web + configured SearXNG')
        u=urllib.parse.urlsplit(self.s.searxng_url)
        if u.username or u.password:raise ValueError('credentials in search URL denied')
        if u.scheme=='http':
            if u.hostname not in ('localhost','127.0.0.1','::1'):
                raise ValueError('only loopback HTTP SearXNG is allowed')
        else:
            assert_public_https(self.s.searxng_url,self.s.domain_allowlist)
        url=self.s.searxng_url.rstrip('/')+'/search?'+urllib.parse.urlencode({'q':query[:200],'format':'json'})
        req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'CognitiveCoreResearch/0.1'})
        # Do not follow redirects to unapproved addresses.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),PublicHTTPSHandler(),NoRedirect())
        with opener.open(req,timeout=self.s.request_timeout_seconds) as r:
            data=json.loads(read_bounded(r,200_000,self.s.request_timeout_seconds))
        candidates=[]
        for x in data.get('results',[]):
            if len(candidates)>=limit:
                break
            link=x.get('url','')
            try:
                assert_public_https(link,self.s.domain_allowlist)
            except (ValueError,OSError):
                continue
            candidates.append({'url':link,'title':x.get('title','')[:200],
                               'snippet':x.get('content','')[:400], 'verified':False})
        return candidates
