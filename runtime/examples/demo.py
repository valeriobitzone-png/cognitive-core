"""Reproducible end-to-end demonstration with no API usage."""
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from worldcore import WorldCore

with TemporaryDirectory() as directory:
    with WorldCore(Path(directory)/'demo.db') as w:
        w.remember('agent','mono.architecture','legacy v1',source='decision')
        w.remember('agent','mono.architecture','world model cognitive layer v2',source='decision')
        print('VERSIONED MEMORY:',w.context_for('agent','mono architecture'))
        w.set_state('agent','failed_tests',4)
        print('COUNTERFACTUAL:',w.simulate('agent',[{'op':'add','key':'failed_tests','value':-2}]))
        w.add_rule('agent','failed_tests','>=',3,'Test failure spike: propose investigation')
        print('PROACTIVE ALERTS:',w.tick('agent'))
        due=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        forecast=w.forecast('agent','Build fails tomorrow',True,0.7,due)
        print('FORECAST:',w.resolve_forecast('agent',forecast['id'],False,allow_early=True))
        print('SCORED LEARNING:',w.forecast_stats('agent'))
