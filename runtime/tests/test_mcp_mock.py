"""MCP registration smoke test with a fake SDK; NOT real host certification."""
import sys,types
from worldcore import WorldCore
from worldcore.mcp_server import create_server


def test_mcp_tools_registration_and_public_search(monkeypatch,tmp_path):
    db=str(tmp_path/'mcp.db')
    with WorldCore(db) as w:
        w.learn_evidence('public_research',{'source':'fixture','record_id':'r1','title':'GIS map software',
           'summary':'Source-attributed GIS data and geometry analysis from public repositories.',
           'kind':'repo','url':'https://github.com/QGIS/QGIS','license':'METADATA-ONLY',
           'published_at':'2026-10-30T00:00:00Z','topics':['maps'],'entities':[]},space='repo_catalog')
    class FakeMCP:
        def __init__(self,*args,**kwargs):self.tools={}
        def tool(self):
            def register(f):self.tools[f.__name__]=f;return f
            return register
    mcp=types.ModuleType('mcp');server=types.ModuleType('mcp.server');fast=types.ModuleType('mcp.server.fastmcp')
    fast.FastMCP=FakeMCP
    monkeypatch.setitem(sys.modules,'mcp',mcp);monkeypatch.setitem(sys.modules,'mcp.server',server)
    monkeypatch.setitem(sys.modules,'mcp.server.fastmcp',fast)
    monkeypatch.setenv('WORLDCORE_DB',db)
    monkeypatch.setenv('WORLDCORE_OWNER','trusted_local');monkeypatch.setenv('WORLDCORE_SPACE','private')
    host=create_server()
    assert {'research_public','research_personalized_news','intelligence_search','intelligence_digest',
            'intelligence_associations','intelligence_temporal_links','intelligence_links',
            'world_imagine','world_reliability','event_market_research','social_velocity',
            'repository_discovery','language_intent','learned_world_dynamics',
            'verified_context_forecast','personal_attention','context_anomaly',
            'world_predict_next','world_simulate_hybrid'} <= set(host.tools)
    assert host.tools['research_public']('GIS')[0]['url']=='https://github.com/QGIS/QGIS'
    assert host.tools['intelligence_search']('GIS')==[]
