"""Real Chromium offline learning test, not an external website or browser integration."""
import json
from pathlib import Path
import pytest
from worldcore import WorldCore
from worldcore.browser_learning import snapshot_page


def make_site(tmp_path,name,positive,negative,layout):
    path=tmp_path/f'{name}.html'
    if layout==1:
        buttons=f'<button onclick="inc()">{positive}</button><button onclick="dec()">{negative}</button>'
    elif layout==2:
        buttons=f'<nav><button onclick="dec()">{negative}</button></nav><section><button aria-label="{positive}" onclick="inc()">+</button></section>'
    else:
        buttons=f'<section><button onclick="dec()">{negative}</button><p>Task organizer</p></section><aside><button role="button" onclick="inc()">{positive}</button></aside>'
    path.write_text(f'''<!doctype html><html><head><title>{name}</title></head><body>
      <p id="counter">0</p>{buttons}
      <script>let n=0;function inc(){{document.querySelector('#counter').textContent=++n;}}
      function dec(){{document.querySelector('#counter').textContent=--n;}}</script>
      </body></html>''',encoding='utf-8')
    return path.as_uri()


def test_real_chromium_unseen_app_and_visual_layout(tmp_path):
    try:from playwright.sync_api import sync_playwright
    except ImportError:pytest.skip('playwright not installed, browser evaluation unavailable')
    with sync_playwright() as p:
        try:browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        except Exception as exc:pytest.skip(f'Chromium unavailable: {exc}')
        with browser:
            with WorldCore(tmp_path/'engine.db') as core:
                # Different applications, button order, accessible labels and DOM structure.
                for name,positive,negative,layout in [('tasksA','Add task','Delete all',1),
                       ('tasksB','Create item','Erase tasks',2),('tasksC','New task','Remove item',3)]:
                    page=browser.new_page()
                    page.set_content(Path(make_site(tmp_path,name,positive,negative,layout).replace("file://", "")).read_text())
                    snap=snapshot_page(page)
                    assert snap['title']==name
                    selected=next(x for x in snap['elements'] if x['label']==positive)
                    before=int(page.locator('#counter').inner_text())
                    page.get_by_role('button',name=positive).click()
                    after=int(page.locator('#counter').inner_text())
                    assert after-before==1
                    core.record_ui_transition('tester',name,'create task',selected,{'count':before},{'count':after},True)
                    page.close()

                # Holdout application has neither the same selector order nor the same text.
                holdout=browser.new_page()
                holdout.set_content(Path(make_site(tmp_path,'unseenSite','New item','Settings',2).replace('file://','')).read_text())
                snap=snapshot_page(holdout)
                prediction=core.suggest_ui_action('tester','create task',snap['elements'])
                assert prediction['status']=='suggested'
                assert prediction['choice']['label']=='New item'
                holdout.get_by_role('button',name='New item').click()
                assert holdout.locator('#counter').inner_text()=='1'
                assert core.suggest_ui_action('tester','delete server',snap['elements'])['status']=='abstain'
                assert core.suggest_ui_action('another_user','create task',snap['elements'])['status']=='abstain'
                holdout.close()


def test_ui_transition_versioned_and_input_values_not_recorded(tmp_path):
    with WorldCore(tmp_path/'ui.db') as core:
        core.record_ui_transition('tester','app','create task',{'label':'Add task','role':'button'},
                                  {'tasks':0,'password':'verysecret'},{'tasks':1,'password':'verysecret'},True)
        row=core.db.execute('SELECT before_json,after_json FROM ui_learning').fetchone()
        assert 'verysecret' not in str(row)
        assert json.loads(row['after_json'])=={'tasks':1}

def test_ui_effect_generalizes_and_abstains_on_unknown(tmp_path):
    with WorldCore(tmp_path/'effects.db') as w:
        for label in ('Add task','Create item','New task'):
            w.record_ui_transition('u','app','create task',{'label':label,'role':'button'},
                {'count':2},{'count':3},True)
        result=w.predict_ui_effect('u','create task',{'label':'New item','role':'button'})
        assert result['status']=='predicted' and result['numeric_state_delta']['count']==1
        assert w.predict_ui_effect('u','create task',{'label':'Destroy everything','role':'button'})['status']=='abstain'
        assert w.predict_ui_effect('other','create task',{'label':'New item','role':'button'})['status']=='abstain'
