"""Hermes native plugin. Install WorldCore package into Hermes' Python environment.

By default only safe tool names, outcomes and duration are stored. Raw user,
assistant and tool-result content is NOT persisted by this adapter.
"""
import os
import json
from worldcore import WorldCore
from worldcore.engine import redact

OWNER = os.environ.get("WORLDCORE_OWNER", "local")
SPACE = os.environ.get("WORLDCORE_SPACE", "default")


def before_llm(session_id="", user_message="", **kwargs):
    try:
        if not user_message or not str(user_message).strip():
            return None
        with WorldCore() as core:
            context = core.context_for(OWNER, str(user_message)[:1000], space=SPACE)
        return {"context":context} if context else None
    except Exception:
        # Memory enrichments are noncritical; never make the host model unavailable.
        return None


def after_tool(tool_name="", args=None, result=None, task_id="", status="", duration_ms=0, **kwargs):
    try:
        if not tool_name: return None
        duration = int(float(duration_ms or 0))
        summary=f"tool={redact(str(tool_name))[:100]} status={redact(str(status or 'unknown'))[:40]} duration_ms={max(0,duration)}"
        with WorldCore() as core:
            core.record_event(OWNER,"tool_completed",summary,space=SPACE,source="hermes",outcome="observed")
    except Exception:
        pass
    return None


def register(ctx):
    ctx.register_hook("pre_llm_call", before_llm)
    ctx.register_hook("post_tool_call", after_tool)
    # Read-only model tools: actual owner authentication is delegated to Hermes host.
    if hasattr(ctx, 'register_tool'):
        def advice_handler(params):
            try:
                with WorldCore() as w:
                    value=w.day_advice(OWNER,params['start_at'],params['end_at'],space=SPACE,
                                       from_place=params.get('from_place'))
                return json.dumps(value,ensure_ascii=False)
            except Exception as exc:
                return json.dumps({'status':'unavailable','error':type(exc).__name__})
        ctx.register_tool(name='worldcore_personal_advice',toolset='worldcore',handler=advice_handler,
          schema={'name':'worldcore_personal_advice',
            'description':'Read authorized calendar/mail metadata and historic commute suggestions. No edits or sending.',
            'parameters':{'type':'object','properties':{
              'start_at':{'type':'string','description':'Timezone-aware ISO start'},
              'end_at':{'type':'string','description':'Timezone-aware ISO end'},
              'from_place':{'type':'string'}},'required':['start_at','end_at']}})
    if hasattr(ctx, 'register_tool'):
        def whatif_handler(params):
            try:
                with WorldCore() as w:
                    result=w.compare_futures(OWNER,params['question'],params['scenarios'],
                      space=SPACE,objectives=params.get('objectives',[]),
                      failure_conditions=params.get('failure_conditions',[]))
                return json.dumps(result,ensure_ascii=False)
            except Exception as exc:
                return json.dumps({'status':'unavailable','error':type(exc).__name__})
        ctx.register_tool(name='worldcore_whatif',toolset='worldcore',handler=whatif_handler,
          schema={'name':'worldcore_whatif',
            'description':'Compare WHAT IF alternatives using evidence, no real actions or authorizations.',
            'parameters':{'type':'object','properties':{
              'question':{'type':'string'},'scenarios':{'type':'array','minItems':2,'maxItems':12,'items':{
                'type':'object','properties':{
                  'id':{'type':'string'},
                  'actions':{'type':'array','maxItems':32,'items':{
                    'type':'object','properties':{
                      'op':{'type':'string','enum':['set','add','delete']},
                      'key':{'type':'string'},'value':{'type':'number'}},
                    'required':['op','key'],'additionalProperties':False}}},
                'required':['id','actions'],'additionalProperties':False}},
              'objectives':{'type':'array','maxItems':8,'items':{
                'type':'object','properties':{
                  'key':{'type':'string'},'direction':{'type':'string','enum':['minimize','maximize']},
                  'scale':{'type':'number','exclusiveMinimum':0}},
                'required':['key','direction'],'additionalProperties':False}},
              'failure_conditions':{'type':'array','items':{'type':'object'}}},
              'required':['question','scenarios','objectives']}})
    if os.environ.get("WORLDCORE_ENABLE_LLM_PROBE") == "1" and hasattr(ctx, "register_command"):
        ctx.register_command(
            name="worldcore-probe",
            handler=lambda raw: str(llm_contract_probe(ctx, raw.strip() if raw and raw.strip() else "What should an agent verify before acting?")),
            description="Opt-in one-shot Hermes host model connectivity test, no memory writes",
            args_hint="[short question]",
        )


def llm_contract_probe(ctx, question='Identify the next useful action for a personal agent.'):
    """OPT-IN one-shot host model probe. No model credentials in plugin.

    Callable only by trusted host harness; not registered on conversation hooks.
    Uses Hermes ctx.llm documented host-owned provider/credentials. The probe
    NEVER trains on returned text or persists a raw answer.
    """
    if os.environ.get('WORLDCORE_ENABLE_LLM_PROBE')!='1':
        return {'status':'disabled','reason':'operator must opt in'}
    if not isinstance(question,str) or not 1<=len(question)<=300:
        return {'status':'invalid_input'}
    llm=getattr(ctx,'llm',None)
    if llm is None:
        return {'status':'unavailable','reason':'Hermes ctx.llm not present'}
    try:
        response=llm.complete(messages=[
            {'role':'system','content':'Give a single short, cautious recommendation. Do not execute actions.'},
            {'role':'user','content':question}],max_tokens=100,temperature=0,timeout=12,purpose='worldcore.contract_probe')
        return {'status':'completed','text':str(response.text)[:1200],
                'model':str(getattr(response,'model','unknown'))[:120],
                'provider':str(getattr(response,'provider','unknown'))[:120]}
    except Exception as exc:
        return {'status':'model_error','error_type':type(exc).__name__}
