"""One synthetic completion via the real Hermes ctx.llm facade, no tool actions."""
import importlib.util
import json
import os
from pathlib import Path
from hermes_cli.plugins import PluginManager,PluginContext
from hermes_cli.plugins_manifest import PluginManifest

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'adapters/hermes/worldcore/__init__.py'
spec=importlib.util.spec_from_file_location('worldcore_probe_adapter',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
manifest=PluginManifest(name='worldcore',version='1.2.0',source='project',path=str(path.parent))
manager=PluginManager(scope_key=os.environ['WORLDCORE_PROBE_SCOPE'])
context=PluginContext(manifest,manager)
result=module.llm_contract_probe(context,'In one short sentence, explain why a forecast needs an uncertainty interval.')
print(json.dumps(result,indent=2))
