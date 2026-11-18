"""Safe, self-contained demonstration. Uses only explicitly synthetic examples."""
from datetime import datetime, timezone, timedelta
from worldcore import WorldCore

now=datetime(2026,10,30,tzinfo=timezone.utc)
with WorldCore(':memory:') as core:
    for i in range(5):
        core.observe_world_transition('local','demo_browser',f'obs_{i}',
             {'screen':'home'},'open_search',{'screen':'results'},source='observed')
    prediction=core.submit_world_prediction('local','demo_browser',{'screen':'home'},'open_search')
    print('WORLD MODEL:',prediction)
    print('UNKNOWN:',core.imagine_world('local','demo_browser',{'screen':'unknown'},['open_search']))
    core.record_skill_feedback('local','task1','browser',True,'Synthetic example succeeded',at=now.isoformat())
    print('SOCIAL:',core.social_velocity('local','instagram','post_123'))
    print('LANGUAGE:',core.classify_intent('local','Mostrami le notizie'))
    print('MARKET:',core.news_market_study('local','macro','BTCUSDT','BENCH'))
