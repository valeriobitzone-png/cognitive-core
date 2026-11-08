"""Run against an explicitly selected, real Hermes checkout and its registries.
No other project component is imported. HERMES_HOME must be a disposable scope.
"""
import json
import os
from pathlib import Path
import sys
from hermes_cli.plugins import PluginManager
from hermes_cli.plugins_manifest import PluginManifest
from tools.registry import registry
from worldcore import WorldCore

ROOT=Path(__file__).resolve().parents[1]
home=Path(os.environ['HERMES_HOME']).resolve()
manager=PluginManager(scope_key=str(home))
manifest=PluginManifest(name='worldcore',version='1.2.0',source='project',path=str(ROOT/'adapters/hermes/worldcore'))
manager._load_plugin(manifest)
loaded=manager._plugins.get('worldcore')
if loaded is None or loaded.error:
    raise RuntimeError('Hermes plugin failed to load: '+str(getattr(loaded,'error',None)))
manager.invoke_hook('post_tool_call',tool_name='read',status='completed',duration_ms=3,args={'secret':'DO_NOT_SAVE'},result='DO_NOT_SAVE')
result=registry.dispatch('worldcore_whatif',{'question':'Real Hermes registry probe','scenarios':[{'id':'a','actions':[]},{'id':'b','actions':[]}],'objectives':[]},scope=str(home))
if isinstance(result,str):result=json.loads(result)
assert result['action_executed'] is False, result
with WorldCore() as w:
    events=w.events(os.environ['WORLDCORE_OWNER'],space=os.environ['WORLDCORE_SPACE'])
    assert any('tool=read' in e['summary'] for e in events),events
    assert 'DO_NOT_SAVE' not in json.dumps(events)
print(json.dumps({'host':'real_installed_Hermes','loader':'PluginManager._load_plugin','registry':'tools.registry.dispatch',
                  'hooks_verified':True,'whatif_verified':True,'metadata_privacy_verified':True,
                  'llm_called':False,'source_checkout':str(Path(__import__('hermes_cli').__file__).parent.parent)},indent=2))
