from worldcore import WorldCore
from worldcore.claude_hook import handle

def test_claude_hook_naked_prompt_does_not_write(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'hooks.db'))
    monkeypatch.setenv('WORLDCORE_OWNER','alpha')
    with WorldCore(tmp_path/'hooks.db') as w:
        w.remember('alpha','project','Build WorldCore',source='operator')
    out=handle({'hook_event_name':'UserPromptSubmit','prompt':'project'})
    assert 'hookSpecificOutput' in out
    assert 'WorldCore' in out['hookSpecificOutput']['additionalContext']
    assert handle({'hook_event_name':'UserPromptSubmit','prompt':''})=={}

def test_claude_hook_metadata_only(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'hooks.db'))
    handle({'hook_event_name':'PostToolUse','tool_name':'Bash','tool_input':{'command':'SECRET=private_value'},'tool_result':'secret'})
    with WorldCore(tmp_path/'hooks.db') as w:
        events=w.events('local')
        assert len(events)==1
        assert 'private_value' not in str(events)
        assert 'Bash' in events[0]['summary']
    assert handle({'hook_event_name':'PostToolUse','tool_name':'rm -rf /'})=={}
