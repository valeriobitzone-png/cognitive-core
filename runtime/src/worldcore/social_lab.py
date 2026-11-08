"""Engagement-velocity analytics, not a guarantee of virality or persuasion engine."""
from __future__ import annotations
from .worldmodel import _valid_atom
from datetime import datetime
import math

class SocialLabMixin:
    def _init_social_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS social_metrics(
         owner TEXT,space TEXT,platform TEXT,post TEXT,at TEXT,views INTEGER,
         shares INTEGER,comments INTEGER,likes INTEGER,source TEXT,
         PRIMARY KEY(owner,space,platform,post,at));
        ''')

    def add_social_snapshot(self,owner,platform,post,at,views,shares,comments,likes,*,source,space='default'):
        from .engine import WorldCoreError, _when
        ids=(owner,space,platform,post,source)
        owner,space,platform,post,source=map(lambda x:_valid_atom(x,'identifier'),ids)
        at=_when(at)
        nums=(views,shares,comments,likes)
        if any(type(x)!=int or not 0<=x<=1_000_000_000_000 for x in nums):
            raise WorldCoreError('metrics must be nonnegative integers')
        if shares>views or comments>views or likes>views:
            raise WorldCoreError('interactions cannot exceed views in this metric contract')
        with self._transaction():
            r=self.db.execute('''SELECT views,shares,comments,likes,source FROM social_metrics
                          WHERE owner=? AND space=? AND platform=? AND post=? AND at=?''',
                        (owner,space,platform,post,at)).fetchone()
            if r:
                if tuple(r)==(*nums,source):return {'status':'unchanged'}
                raise WorldCoreError('conflicting social snapshot')
            prev=self.db.execute('''SELECT views,shares,comments,likes FROM social_metrics
                       WHERE owner=? AND space=? AND platform=? AND post=? AND at<? ORDER BY at DESC LIMIT 1''',
                       (owner,space,platform,post,at)).fetchone()
            if prev and any(v<prev[k] for v,k in zip(nums,('views','shares','comments','likes'))):
                raise WorldCoreError('cumulative metrics cannot decrease within this source')
            self.db.execute('INSERT INTO social_metrics VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (owner,space,platform,post,at,*nums,source))
        return {'status':'recorded'}

    def social_velocity(self,owner,platform,post,*,space='default'):
        from .engine import WorldCoreError
        owner,space,platform,post=map(lambda x:_valid_atom(x,'identifier'),(owner,space,platform,post))
        with self.lock:
            rows=self.db.execute('''SELECT * FROM social_metrics WHERE owner=? AND space=? AND platform=? AND post=? ORDER BY at DESC LIMIT 2''',
                                 (owner,space,platform,post)).fetchall()
        if len(rows)<2:return {'status':'abstain','reason':'requires_two_snapshots'}
        a,b=rows[0],rows[1]
        hours=(datetime.fromisoformat(a['at'])-datetime.fromisoformat(b['at'])).total_seconds()/3600
        if hours<=0:raise WorldCoreError('invalid timing')
        deltas={k:a[k]-b[k] for k in ('views','shares','comments','likes')}
        if any(v<0 for v in deltas.values()):return {'status':'abstain','reason':'inconsistent_cumulative_counts'}
        rate=lambda v:round(v/hours,5)
        # weighted interaction ratio; descriptive only, NOT universal "viral score".
        engagement=(deltas['shares']*3+deltas['comments']*2+deltas['likes'])/max(1,deltas['views'])
        return {'status':'descriptive_only','hours':round(hours,4),'deltas':deltas,
                'views_per_hour':rate(deltas['views']),'shares_per_hour':rate(deltas['shares']),
                'weighted_engagement_per_new_view':round(engagement,6),
                'notice':'not normalized for algorithm, audience, paid amplification or cross-platform bias; no virality guarantee'}
