"""Chromium holdout across synthetic unseen web apps; no external navigation."""
from pathlib import Path
import json,tempfile
from playwright.sync_api import sync_playwright
from worldcore import WorldCore
from worldcore.browser_learning import snapshot_page

def html(positive,negative,variant):
    buttons=([f'<button onclick="add()">{negative}</button>',
              f'<button aria-label="{positive}" onclick="add()">+</button>'] if variant%2
             else [f'<div><button onclick="add()">{positive}</button></div>',
                   f'<nav><button onclick="subtract()">{negative}</button></nav>'])
    # Repair distractor: should subtract, never increase.
    buttons[0]=buttons[0].replace(f'onclick="add()">{negative}',f'onclick="subtract()">{negative}')
    return f'''<html><head><title>holdout-{variant}</title></head><body><span id="count">0</span>
        {''.join(buttons)}<script>let x=0; function add(){{document.getElementById('count').textContent=++x;}}
        function subtract(){{document.getElementById('count').textContent=--x;}}</script></body></html>'''

def run():
    with tempfile.TemporaryDirectory() as directory:
        with WorldCore(Path(directory)/'browser.db') as core:
            for name in ['Add task','Create item','New task']:
                core.record_ui_transition('test','training','create task',{'role':'button','label':name},
                      {'count':0},{'count':1},True)
            successes=0;total=0;abstained=0
            with sync_playwright() as p, p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']) as browser:
                for i,positive in enumerate(['New item','Create task','Add item','New task','Create item','Add task']):
                    page=browser.new_page();page.set_content(html(positive,'Settings',i))
                    snap=snapshot_page(page)
                    pred=core.suggest_ui_action('test','create task',snap['elements'])
                    if pred['status']=='suggested':
                        page.get_by_role('button',name=pred['choice']['label']).click()
                        successes+=int(page.locator('#count').inner_text()=='1')
                    total+=1;page.close()
                for i in range(4):
                    page=browser.new_page();page.set_content(html('Run upgrade','Settings',i))
                    pred=core.suggest_ui_action('test','create task',snapshot_page(page)['elements'])
                    abstained+=pred['status']=='abstain';page.close()
            report={'heldout_synthetic_apps':total,'successful_offline_browser_actions':successes,
                    'unknown_affordance_abstentions':abstained,'unknown_tests':4,
                    'restrictions':'Synthetic local HTML apps using real Chromium, no outside web, no general browsing'}
    dest=Path('training-artifacts/v10_browser_holdout.json')
    dest.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':run()
