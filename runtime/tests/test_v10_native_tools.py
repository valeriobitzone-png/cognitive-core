import importlib.util,json
from pathlib import Path
from worldcore import WorldCore

def test_hermes_native_tool_registered_and_read_only(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'db.sqlite'))
    import worldcore
    path=Path(__file__).resolve().parents[1]/'adapters/hermes/worldcore/__init__.py'
    spec=importlib.util.spec_from_file_location('wc_hermes_v10',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    collected={}
    class Host:
        def register_hook(self,*a):pass
        def register_tool(self,**kwargs):collected[kwargs['name']]=kwargs
    mod.register(Host())
    assert 'worldcore_personal_advice' in collected
    with WorldCore(tmp_path/'db.sqlite') as core:
        core.put_calendar_event('local','e1','Appointment','2031-01-01T09:00:00Z','2031-01-01T10:00:00Z')
    result=json.loads(collected['worldcore_personal_advice']['handler']({
      'start_at':'2031-01-01T08:00:00Z','end_at':'2031-01-01T12:00:00Z'}))
    assert result['events'][0]['event_id']=='e1'
    assert result['events'][0]['no_automatic_action'] is True
