"""Real Xvfb/Tk smoke test of cross-surface affordance transfer in isolation."""
from pathlib import Path
import os,subprocess,time
import pytest
from worldcore import WorldCore
from worldcore.desktop_learning import snapshot_tk

def test_tk_desktop_unknown_layout_can_use_browser_affordances(tmp_path,monkeypatch):
    import shutil
    if not shutil.which('Xvfb'): pytest.skip('no Xvfb')
    import tkinter as tk
    # Dedicated display with Xvfb; kill the child in all exit paths.
    display=':137'
    server=subprocess.Popen(['Xvfb',display,'-screen','0','800x600x24','-nolisten','tcp'],
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    prev=os.environ.get('DISPLAY')
    try:
        os.environ['DISPLAY']=display
        root=None
        for i in range(20):
            try:root=tk.Tk();break
            except tk.TclError:time.sleep(.15)
        if root is None:pytest.skip('headless display unavailable')
        root.withdraw()
        try:
            count={'value':0}
            tk.Button(root,text='Settings',command=lambda:count.update(value=-99)).pack()
            tk.Frame(root).pack()
            tk.Button(root,text='New item',command=lambda:count.update(value=count['value']+1)).pack()
            with WorldCore(tmp_path/'ui.db') as core:
                for label in ('Create task','Add item','New task'):
                    core.record_ui_transition('alice','browser-app','create task',{'label':label,'role':'button'},
                                              {'count':0},{'count':1},True)
                observation=snapshot_tk(root)
                prediction=core.suggest_ui_action('alice','create task',observation['elements'])
                assert prediction['status']=='suggested' and prediction['choice']['label']=='New item'
                widget=next(x for x in root.winfo_children() if x.winfo_class()=='Button' and x.cget('text')=='New item')
                widget.invoke()
                assert count['value']==1
        finally:root.destroy()
    finally:
        if prev is None:os.environ.pop('DISPLAY',None)
        else:os.environ['DISPLAY']=prev
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait()
