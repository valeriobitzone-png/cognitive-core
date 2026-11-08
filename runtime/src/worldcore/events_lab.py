"""Leakage-aware retrospective event studies for news and markets; analytics only.

Never produces an order or return prediction. News links are observations, not
causal claims. Requires exact timed real samples and benchmark closing prices.
"""
from __future__ import annotations
from datetime import datetime, timedelta
import math, statistics
from .worldmodel import _valid_atom

class EventsLabMixin:
    def _init_events_lab_schema(self):
        self.db.executescript('''
         CREATE TABLE IF NOT EXISTS market_ticks(
          owner TEXT,space TEXT,symbol TEXT,at TEXT,close REAL,source TEXT,
          PRIMARY KEY(owner,space,symbol,at));
         CREATE TABLE IF NOT EXISTS news_marks(
          owner TEXT,space TEXT,id TEXT,topic TEXT,at TEXT,title TEXT,url TEXT,source TEXT,
          PRIMARY KEY(owner,space,id));
         CREATE INDEX IF NOT EXISTS news_topic ON news_marks(owner,space,topic,at);
        ''')

    def record_price(self,owner,symbol,at,close,*,source,space='default'):
        from .engine import _when, WorldCoreError
        owner,space,symbol=_valid_atom(owner,'owner'),_valid_atom(space,'space'),_valid_atom(symbol,'symbol')
        at=_when(at)
        if isinstance(close,bool) or not isinstance(close,(int,float)) or not math.isfinite(close) or close<=0:
            raise WorldCoreError('price must be positive finite')
        source=_valid_atom(source,'source')
        with self._transaction():
            r=self.db.execute('SELECT close,source FROM market_ticks WHERE owner=? AND space=? AND symbol=? AND at=?',(owner,space,symbol,at)).fetchone()
            if r:
                if r['close']==close and r['source']==source:return {'status':'unchanged'}
                raise WorldCoreError('conflicting immutable price sample')
            self.db.execute('INSERT INTO market_ticks VALUES(?,?,?,?,?,?)',(owner,space,symbol,at,float(close),source))
        return {'status':'recorded'}

    def record_news(self,owner,id,topic,at,title,url,*,source,space='default'):
        from .intelligence import _url, _txt
        from .engine import _when, WorldCoreError
        owner,space,id,topic,source=[_valid_atom(v,n) for v,n in ((owner,'owner'),(space,'space'),(id,'news id'),(topic,'topic'),(source,'source'))]
        at=_when(at);title=_txt(title,240);url=_url(url)
        with self._transaction():
            row=self.db.execute('SELECT topic,at,title,url,source FROM news_marks WHERE owner=? AND space=? AND id=?',(owner,space,id)).fetchone()
            if row:
                if tuple(row)==(topic,at,title,url,source):return {'status':'unchanged'}
                raise WorldCoreError('conflicting news event')
            self.db.execute('INSERT INTO news_marks VALUES(?,?,?,?,?,?,?,?)',(owner,space,id,topic,at,title,url,source))
        return {'status':'recorded','notice':'headline is an attributed report, not a verified fact'}

    def news_market_study(self,owner,topic,symbol,benchmark,*,space='default',horizon_hours=24,
                          min_events=5, max_gap_hours=12):
        """Measure forward excess log-return using prices observed near event and horizon.

        Uses calendar time and fixed look-forward duration, never same-bar outcome labels.
        No p-values from iid assumptions: clustered/autocorrelated events may invalidate them.
        """
        from .engine import WorldCoreError
        owner,space,topic,symbol,benchmark=map(lambda x:_valid_atom(x,'identifier'),
                                        (owner,space,topic,symbol,benchmark))
        if symbol==benchmark:raise WorldCoreError('benchmark must differ from symbol')
        if not isinstance(horizon_hours,int) or not 1<=horizon_hours<=720 or not isinstance(max_gap_hours,int) or not 1<=max_gap_hours<=48 or not isinstance(min_events,int) or not 3<=min_events<=1000:
            raise WorldCoreError('invalid study parameters')
        with self.lock:
            events=self.db.execute('SELECT * FROM news_marks WHERE owner=? AND space=? AND topic=? ORDER BY at',(owner,space,topic)).fetchall()
            prices={}
            for s in (symbol,benchmark):
                prices[s]=[(datetime.fromisoformat(r['at']),float(r['close'])) for r in self.db.execute(
                    'SELECT at,close FROM market_ticks WHERE owner=? AND space=? AND symbol=? ORDER BY at',(owner,space,s))]
        def close_after(series,start):
            # Strict upper bound on latency. Price immediately following publication is not assumed pre-news.
            for t,p in series:
                if t>=start and t-start<=timedelta(hours=max_gap_hours):return t,p
            return None
        out=[];excluded={'missing_price':0,'overlap':0};last_window=None
        for ev in events:
            start=datetime.fromisoformat(ev['at']);end=start+timedelta(hours=horizon_hours)
            if last_window and start<last_window:
                excluded['overlap']+=1;continue
            p0=close_after(prices[symbol],start);b0=close_after(prices[benchmark],start)
            p1=close_after(prices[symbol],end);b1=close_after(prices[benchmark],end)
            if not (p0 and p1 and b0 and b1):excluded['missing_price']+=1;continue
            if p1[0]<=p0[0] or b1[0]<=b0[0]:excluded['missing_price']+=1;continue
            asset=math.log(p1[1]/p0[1]);bench=math.log(b1[1]/b0[1]);excess=asset-bench
            out.append({'news_id':ev['id'],'published_at':ev['at'],'excess_log_return':round(excess,8),
                        'asset_log_return':round(asset,8),'benchmark_log_return':round(bench,8),
                        'start_used':p0[0].isoformat(),'end_used':p1[0].isoformat()})
            last_window=end
        if len(out)<min_events:
            return {'status':'abstain','reason':'insufficient_independent_events',
                    'qualified_events':len(out),'required':min_events,'excluded':excluded}
        xs=[x['excess_log_return'] for x in out]
        return {'status':'retrospective_only','topic':topic,'asset':symbol,'benchmark':benchmark,
                'horizon_hours':horizon_hours,'events':len(out),'mean_excess_log_return':round(statistics.mean(xs),8),
                'median_excess_log_return':round(statistics.median(xs),8),'positive_fraction':round(sum(x>0 for x in xs)/len(xs),5),
                'excluded':excluded,'details':out[:100],
                'limitations':['association is not causation','event selection and timing can bias results',
                               'market regime and multiple testing require out-of-sample validation',
                               'no trade signal or investment recommendation']}
