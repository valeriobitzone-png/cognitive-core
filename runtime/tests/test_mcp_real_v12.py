"""Real MCP SDK, stdio transport and engine; no simulated host, no LLM."""
import asyncio
import json
import os
from pathlib import Path
import sys
import pytest


def test_real_sdk_stdio_roundtrip(tmp_path):
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def run():
        env={**os.environ,'WORLDCORE_DB':str(tmp_path/'mcp.db'),'WORLDCORE_OWNER':'actual_sdk_host','WORLDCORE_SPACE':'isolated'}
        params=StdioServerParameters(command=sys.executable,args=['-m','worldcore.mcp_server'],env=env)
        async with asyncio.timeout(12):
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer) as session:
                    initialized=await session.initialize()
                    assert initialized.serverInfo.name=='WorldCore'
                    tools=(await session.list_tools()).tools
                    names={tool.name for tool in tools}
                    assert {'whatif_compare','calibrated_world_predict','calibrated_world_metrics'}<=names
                    assert 'approve_action' not in names
                    saved=await session.call_tool('memory_save',{'key':'probe','value':'local integration fixture'})
                    assert not saved.isError
                    result=await session.call_tool('whatif_compare',{'question':'Test alternatives','scenarios':[{'id':'a','actions':[]},{'id':'b','actions':[]}],'objectives':[]})
                    assert not result.isError
                    data=json.loads(result.content[0].text)
                    assert data['action_executed'] is False
                    unavailable=await session.call_tool('calibrated_world_predict',{'family':'unknown','before':{'x':1},'action':'move'})
                    assert json.loads(unavailable.content[0].text)['status']=='abstain'
                    # Tenant identity is operator-bound and never a model parameter.
                    schema=next(t.inputSchema for t in tools if t.name=='calibrated_world_predict')
                    assert 'owner' not in schema['properties']
    asyncio.run(run())
