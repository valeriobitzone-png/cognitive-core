"""Explicit-authority MCP action gateway.

No arbitrary shell, HTTP, financial trade or health/medical actions. Only
operator allowlisted local side effects, after one-time externally granted approval.
The MCP client cannot approve itself. Crash after consume => unknown/manual reconcile,
never blind retry. Write-once receipts permit auditing.
"""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from .worldmodel import _valid_atom

VALID_ACTIONS={'note.create','task.create'}

class ActionGatewayMixin:
    def _init_action_gateway_schema(self):
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS action_receipts(
            request_id TEXT PRIMARY KEY,owner TEXT NOT NULL,space TEXT NOT NULL,
            action TEXT NOT NULL,status TEXT NOT NULL,artifact TEXT,
            executed_at TEXT NOT NULL,details TEXT NOT NULL);
        ''')

    def propose_real_action(self,owner,action,args,purpose,*,space='default',ttl_seconds=900):
        from .engine import WorldCoreError
        if action not in VALID_ACTIONS:raise WorldCoreError('action not allowlisted')
        self._validate_action_args(action,args)
        return self.request_action(owner,action,args,purpose,space=space,ttl_seconds=ttl_seconds)

    @staticmethod
    def _validate_action_args(action,args):
        from .engine import WorldCoreError
        if not isinstance(args,dict):raise WorldCoreError('args must be an object')
        if action=='note.create':
            if set(args)!={'title','body'}:raise WorldCoreError('note requires title and body')
            if not isinstance(args['title'],str) or not 1<=len(args['title'].strip())<=120:raise WorldCoreError('invalid title')
            if not isinstance(args['body'],str) or not 1<=len(args['body'].strip())<=4000:raise WorldCoreError('invalid body')
        elif action=='task.create':
            if set(args)!={'description','due_at'}:raise WorldCoreError('task requires description and due_at')
            if not isinstance(args['description'],str) or not 1<=len(args['description'].strip())<=300:raise WorldCoreError('invalid description')
            from .engine import _when
            _when(args['due_at'])
        else:raise WorldCoreError('action not allowlisted')
        for v in args.values():
            if isinstance(v,str) and '\x00' in v:raise WorldCoreError('NUL forbidden')

    def action_receipt(self,owner,request_id,*,space='default'):
        owner,space,request_id=[_valid_atom(x,'identifier') for x in (owner,space,request_id)]
        with self.lock:
            row=self.db.execute('SELECT * FROM action_receipts WHERE owner=? AND space=? AND request_id=?',(owner,space,request_id)).fetchone()
        return dict(row) if row else None

    def execute_approved_action(self,owner,request_id,action,args,*,space='default',root=None):
        """Local side effect, never exposes arbitrary host tools.

        Host MUST authenticate identity; operator approves out-of-band.
        `root` only from trusted host config; never passed by MCP tool caller.
        No remote/network API or third-party execution.
        """
        from .engine import WorldCoreError,utcnow
        owner,space,request_id,action=[_valid_atom(x,'identifier') for x in (owner,space,request_id,action)]
        if action not in VALID_ACTIONS:raise WorldCoreError('action not allowlisted')
        self._validate_action_args(action,args)
        base=root or os.environ.get('WORLDCORE_ACTION_ROOT')
        if not base:raise WorldCoreError('operator must configure WORLDCORE_ACTION_ROOT')
        base=Path(base).expanduser()
        # The operator-controlled root is never selected by the model/MCP caller.
        if base.is_symlink():raise WorldCoreError('symlink root forbidden')
        base.mkdir(mode=0o700,parents=True,exist_ok=True)
        if not base.is_dir():raise WorldCoreError('action root not a directory')
        if not self.consume_approval(owner,request_id,action,args,space=space):
            raise WorldCoreError('not approved, expired, wrong args, or already used')
        # State has already changed to consumed. Do not replay if anything fails.
        target=base / ('notes' if action=='note.create' else 'tasks')
        try:
            if target.is_symlink():raise WorldCoreError('symlink target folder forbidden')
            target.mkdir(mode=0o700,exist_ok=True)
            identifier=request_id+'.json'
            location=target / identifier
            body={'request_id':request_id,'owner':owner,'space':space,'action':action,'args':args,'at':utcnow()}
            flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
            if hasattr(os,'O_NOFOLLOW'):flags|=os.O_NOFOLLOW
            fd=os.open(str(location),flags,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as file:
                json.dump(body,file,ensure_ascii=False,sort_keys=True)
                file.flush();os.fsync(file.fileno())
            if action=='task.create':
                self.record_task_expectation(owner,request_id,args['description'],args['due_at'],space=space,source='action_gateway')
            status='completed';detail='local persisted artifact created'
            artifact=str(location)
        except Exception as exc:
            status='unknown_or_failed';detail=f'{type(exc).__name__}: local side effect requires manual reconciliation'
            artifact=None
        with self._transaction():
            self.db.execute('''INSERT INTO action_receipts VALUES (?,?,?,?,?,?,?,?)''',
                (request_id,owner,space,action,status,artifact,utcnow(),detail))
        return {'status':status,'request_id':request_id,'action':action,'artifact':artifact,
                'retriable':False,'details':detail}
