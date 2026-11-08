"""Optional consented desktop UI adapter for Tk test applications.

Not a cross-OS accessibility provider. Production integrations should provide
accessibility tree snapshots using the host's native APIs and explicit approval.
No global screen capture, keyboard injection or automatic clicking.
"""
from __future__ import annotations

def snapshot_tk(root):
    """Inspect visible Tk UI widget roles/text without reading entry values."""
    widgets=[]
    def walk(parent):
        for child in parent.winfo_children():
            role=child.winfo_class().lower()
            if role in ('button','tbutton'):
                try:label=str(child.cget('text'))[:120]
                except Exception:label=''
                widgets.append({'label':label,'role':'button'})
            walk(child)
    walk(root)
    return {'elements':widgets, 'modality':'desktop_accessibility_adapter'}
