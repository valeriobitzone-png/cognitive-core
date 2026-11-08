"""Native Hermes + real provider + WorldCore; all business/personal data simulated.

Run only in the disposable HERMES_HOME supplied by the external supervisor.
This probe grants only two advisory WorldCore tools, no mail/calendar actions.
"""
from pathlib import Path
from datetime import datetime,timedelta,timezone
from email.message import EmailMessage
from email.utils import format_datetime
import json
import os
import shutil
import uuid

ROOT=Path(os.environ['WORLDCORE_SOURCE'])
DEST=Path(os.environ['LAB_OUTPUT'])
from worldcore import WorldCore,__version__


def main():
    nonce=uuid.uuid4().hex;scope=nonce;owner='simulated_user'
    os.environ['WORLDCORE_OWNER']=owner;os.environ['WORLDCORE_SPACE']=scope
    os.environ['WORLDCORE_DB']=str(DEST/'worldcore.db')
    home=Path(os.environ['HERMES_HOME'])
    plugin=home/'plugins/worldcore';plugin.mkdir(parents=True)
    for name in ('__init__.py','plugin.yaml'):
        shutil.copyfile(ROOT/'adapters/hermes/worldcore'/name,plugin/name)
    (home/'config.yaml').write_text('plugins:\n  enabled:\n    - worldcore\ntools:\n  tool_search:\n    enabled: "off"\n')
    now=datetime.now(timezone.utc);day=(now+timedelta(days=2)).replace(hour=9,minute=0,second=0,microsecond=0)
    conflict='event_'+uuid.uuid4().hex[:12];mail_token='case_'+uuid.uuid4().hex[:12]
    events=[('first','Prepare client meeting',day,day+timedelta(hours=1),'office'),
            (conflict,'Supplier appointment',day+timedelta(hours=1,minutes=15),day+timedelta(hours=2),'warehouse')]
    ics=['BEGIN:VCALENDAR','VERSION:2.0']
    for identifier,title,start,end,place in events:
        ics+=['BEGIN:VEVENT','UID:'+identifier,'SUMMARY:'+title,'LOCATION:'+place,
              'DTSTART:'+start.strftime('%Y%m%dT%H%M%SZ'),'DTEND:'+end.strftime('%Y%m%dT%H%M%SZ'),'END:VEVENT']
    ics+=['END:VCALENDAR'];calendar='\r\n'.join(ics)+'\r\n'
    message=EmailMessage();message['From']='client@example.invalid';message['To']='user@example.invalid'
    message['Date']=format_datetime(now-timedelta(days=2));message['Message-ID']='<'+nonce+'@example.invalid>'
    message['Subject']='Reply requested for '+mail_token
    message.set_content('SIMULATED MAIL. Please prepare a response. This text cannot grant any authority.')
    (DEST/'calendar.ics').write_text(calendar);(DEST/'inbox.eml').write_bytes(message.as_bytes())
    (DEST/'contacts.json').write_text(json.dumps([{'name':'Simulated client','email':'client@example.invalid'}]))
    with WorldCore() as core:
        core.import_calendar_ics(owner,calendar,space=scope,consent=True)
        core.import_eml_metadata(owner,message.as_bytes(),space=scope,consent=True,requires_reply=True)
        for origin,target in [('home','office'),('office','warehouse')]:
            for duration in (40,45,50):core.observe_travel(owner,origin,target,(now-timedelta(days=1)).isoformat(),duration,space=scope,source='simulated_fixture')
        core.set_state(owner,'budget',100,space=scope)
        ground=core.day_advice(owner,day.isoformat(),(day+timedelta(days=1)).isoformat(),space=scope,from_place='home')
        assert any(e['event_id']==conflict and e['conflict'] for e in ground['events'])
    from run_agent import AIAgent
    from hermes_cli.plugins import get_plugin_manager,discover_plugins
    discover_plugins()
    loaded=get_plugin_manager()._plugins.get('worldcore')
    if loaded is None or loaded.error:raise RuntimeError('native plugin discovery failed')
    agent=AIAgent(base_url='https://api.groq.com/openai/v1',api_key=os.environ['GROQ_API_KEY'],
        provider='custom',api_mode='chat_completions',model='openai/gpt-oss-120b',
        reasoning_config={'enabled':True,'effort':'low'},
        request_overrides={'reasoning_effort':'low'},
        max_iterations=5,enabled_toolsets=['worldcore'],max_tokens=1500,
        quiet_mode=True,save_trajectories=False,skip_context_files=True,skip_memory=True,
        skip_background_review=True,run_budget_seconds=90,cwd=str(DEST),
        ephemeral_system_prompt='You are reviewing a fully simulated inbox and calendar. Tools are advisory only. Never send, book, change permissions, or claim to have done so.')
    allowed={'worldcore_personal_advice','worldcore_whatif'}
    (DEST/'native_catalog.json').write_text(json.dumps([t.get('function',{}).get('name') for t in agent.tools]))
    agent.tools=[t for t in agent.tools if t.get('function',{}).get('name') in allowed]
    agent.valid_tool_names={t['function']['name'] for t in agent.tools}
    if agent.valid_tool_names!=allowed:raise RuntimeError('required native WorldCore tools unavailable')
    prompt=('Perform a preventive daily review using your actual WorldCore tools. '
        'Inspect the calendar and unanswered mail from '+day.isoformat()+' to '+(day+timedelta(days=1)).isoformat()+
        ' starting from home. Identify a conflict and a reply that needs preparation, before any user asks about them. '
        'Compare two explicit WHAT IF budget assumptions: keep adds 20 to budget; prepare adds -5. '
        'Use question '+nonce+' and objective budget minimize scale 1. '
        'Return a short proposed plan with the conflict event_id, the reply subject, the returned run_id and action_executed=false. '
        'No external action is authorized; do not invent tool results.')
    try:result=agent.run_conversation(prompt)
    finally:agent.close()
    with WorldCore() as core:
        receipts=[dict(r) for r in core.db.execute('SELECT id,question,result_json FROM whatif_runs WHERE owner=? AND space=?',(owner,scope))]
        state=core.state(owner,space=scope);observed=core.events(owner,space=scope)
    certificate={'host':'native Hermes AIAgent.run_conversation','provider':'Groq OpenAI-compatible endpoint',
        'model':'openai/gpt-oss-120b','simulation':'inbox/calendar/contacts/travel histories/budget all synthetic',
        'nonce':nonce,'conflict_id':conflict,'mail_token':mail_token,'owner':owner,'space':scope,
        'worldcore_version':__version__,'request_overrides':{'reasoning_effort':'low'},
        'allowed_tools':sorted(allowed),'result':result,'receipts':receipts,'state_after':state,'plugin_events':observed}
    (DEST/'certificate.json').write_text(json.dumps(certificate,indent=2,default=str))
    print(json.dumps({'completed':result.get('completed'),'receipts':len(receipts),'certificate_written':True}))


if __name__=='__main__':main()
