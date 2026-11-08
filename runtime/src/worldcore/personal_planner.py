"""Consent-based calendar, email and travel state for an LLM-agnostic personal agent.

Not a calendar/email connector. All inputs must be authorized and authenticated by
an upstream host. No access to user accounts and no outbound actions here.
Times are timezone-aware, stored in UTC. Commute predictions use observed durations,
with fallback abstention instead of fabricated travel estimates.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
import math
import statistics
from .worldmodel import _valid_atom


def parse_time(value):
    from .engine import WorldCoreError
    if not isinstance(value,str):raise WorldCoreError('timezone-aware time required')
    try:dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as exc:raise WorldCoreError('invalid timestamp') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:raise WorldCoreError('timezone required')
    return dt.astimezone(timezone.utc)

class PersonalPlannerMixin:
    def _init_personal_planner_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS calendar_records (
         owner TEXT NOT NULL,space TEXT NOT NULL,event_id TEXT NOT NULL,revision INTEGER NOT NULL,
         title TEXT NOT NULL,start_at TEXT NOT NULL,end_at TEXT NOT NULL,place TEXT NOT NULL,
         source TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,
         PRIMARY KEY(owner,space,event_id,revision));
        CREATE TABLE IF NOT EXISTS mail_signals (
         owner TEXT NOT NULL,space TEXT NOT NULL,signal_id TEXT NOT NULL,
         received_at TEXT NOT NULL,subject TEXT NOT NULL,requires_reply INTEGER NOT NULL,
         replied INTEGER NOT NULL,deadline TEXT,source TEXT NOT NULL,
         PRIMARY KEY(owner,space,signal_id));
        CREATE TABLE IF NOT EXISTS travel_samples (
         owner TEXT NOT NULL,space TEXT NOT NULL,origin TEXT NOT NULL,destination TEXT NOT NULL,
         observed_at TEXT NOT NULL,minutes REAL NOT NULL,source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS slot_feedback (
         owner TEXT NOT NULL,space TEXT NOT NULL,slot_hour INTEGER NOT NULL,
         positive INTEGER NOT NULL,at TEXT NOT NULL);
        ''')

    def put_calendar_event(self,owner,event_id,title,start_at,end_at,*,space='default',place='remote',source='calendar_authorized',status='confirmed'):
        from .engine import WorldCoreError, _when
        owner,space,event_id,source=[_valid_atom(x,'identifier') for x in (owner,space,event_id,source)]
        if not isinstance(title,str) or not 1<=len(title.strip())<=240:raise WorldCoreError('invalid event title')
        if not isinstance(place,str) or not 1<=len(place.strip())<=128:raise WorldCoreError('invalid location')
        if status not in {'confirmed','cancelled','tentative'}:raise WorldCoreError('invalid event status')
        s,e=parse_time(start_at),parse_time(end_at)
        if e<=s or e-s>timedelta(days=7):raise WorldCoreError('event duration invalid')
        with self._transaction():
            row=self.db.execute('SELECT COALESCE(MAX(revision),0) n FROM calendar_records WHERE owner=? AND space=? AND event_id=?',(owner,space,event_id)).fetchone()
            rev=row['n']+1
            self.db.execute('INSERT INTO calendar_records VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (owner,space,event_id,rev,title.strip(),s.isoformat(),e.isoformat(),place.strip(),source,status,_when()))
        return {'event_id':event_id,'revision':rev,'status':status}

    def calendar_window(self,owner,start_at,end_at,*,space='default'):
        from .engine import WorldCoreError
        owner,space=[_valid_atom(x,'identifier') for x in (owner,space)]
        start,end=parse_time(start_at),parse_time(end_at)
        if end<=start or end-start>timedelta(days=31):raise WorldCoreError('invalid calendar window')
        with self.lock:
            rows=self.db.execute('''SELECT a.* FROM calendar_records a JOIN
                (SELECT event_id,MAX(revision) n FROM calendar_records WHERE owner=? AND space=? GROUP BY event_id) v
                ON a.event_id=v.event_id AND a.revision=v.n WHERE a.owner=? AND a.space=?
                AND a.start_at<? AND a.end_at>? AND a.status!='cancelled' ORDER BY a.start_at''',
                (owner,space,owner,space,end.isoformat(),start.isoformat())).fetchall()
        return [dict(r) for r in rows]

    def import_calendar_ics(self,owner,data,*,space='default',consent=False):
        from .engine import WorldCoreError
        from .personal_imports import parse_calendar_ics
        if consent is not True:raise WorldCoreError('explicit import consent required')
        doc=parse_calendar_ics(data)
        created=[]
        for row in doc['events']:
            if row['status'] not in {'confirmed','tentative','cancelled'}:
                doc['warnings'].append('unknown_status_skipped');continue
            created.append(self.put_calendar_event(owner,row['event_id'],row['title'],row['start_at'],row['end_at'],
                space=space,place=row['place'],source='consented_local_ics',status=row['status']))
        return {'count':len(created),'warnings':sorted(set(doc['warnings'])),
                'limitations':doc['limitations']}

    def import_eml_metadata(self,owner,blob,*,space='default',consent=False,requires_reply=False):
        from .engine import WorldCoreError,redact
        from .personal_imports import parse_eml_header_metadata
        if consent is not True:raise WorldCoreError('explicit import consent required')
        if type(requires_reply) is not bool:raise WorldCoreError('invalid mail flags')
        owner,space=[_valid_atom(v,'identifier') for v in (owner,space)]
        item=parse_eml_header_metadata(blob)
        # Import only metadata. Re-reading a file cannot erase a known reply or
        # deadline supplied by a richer inbox integration.
        with self._transaction():
            self.db.execute('''INSERT INTO mail_signals VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(owner,space,signal_id) DO UPDATE SET
                subject=excluded.subject,requires_reply=excluded.requires_reply''',
                (owner,space,item['signal_id'],item['received_at'],redact(item['subject']),
                 int(requires_reply),0,None,'consented_local_eml'))
        return {'signal_id':item['signal_id'],'stored_metadata_only':True}

    def put_mail_signal(self,owner,signal_id,received_at,subject,*,space='default',requires_reply=True,replied=False,deadline=None,source='mail_authorized'):
        from .engine import WorldCoreError, _when,redact
        owner,space,signal_id,source=[_valid_atom(x,'identifier') for x in (owner,space,signal_id,source)]
        if not isinstance(subject,str) or not 1<=len(subject)<=240:raise WorldCoreError('invalid mail subject')
        if type(requires_reply)!=bool or type(replied)!=bool:raise WorldCoreError('invalid mail flags')
        ts=parse_time(received_at).isoformat()
        dl=parse_time(deadline).isoformat() if deadline else None
        with self._transaction():
            self.db.execute('''INSERT INTO mail_signals VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(owner,space,signal_id) DO UPDATE SET requires_reply=excluded.requires_reply,
                   replied=excluded.replied,deadline=excluded.deadline,subject=excluded.subject''',
                    (owner,space,signal_id,ts,redact(subject),int(requires_reply),int(replied),dl,source))
        return {'signal_id':signal_id,'stored_metadata_only':True}

    def mail_attention(self,owner,*,space='default',now=None,max_days=21):
        owner,space=[_valid_atom(x,'identifier') for x in (owner,space)]
        current=parse_time(now) if now else datetime.now(timezone.utc)
        with self.lock:
            rows=self.db.execute('''SELECT * FROM mail_signals WHERE owner=? AND space=? AND requires_reply=1 AND replied=0''',(owner,space)).fetchall()
        out=[]
        for r in rows:
            if (current-parse_time(r['received_at'])).days>max_days:continue
            deadline=parse_time(r['deadline']) if r['deadline'] else None
            out.append({'signal_id':r['signal_id'],'subject':r['subject'],'hours_since_received':round((current-parse_time(r['received_at'])).total_seconds()/3600,1),
                        'deadline':r['deadline'],'urgent':bool(deadline and deadline<current+timedelta(hours=24)),
                        'suggestion':'Consider replying; no message was sent','evidence':'authorized_mail_metadata'})
        return sorted(out,key=lambda x:(not x['urgent'],-x['hours_since_received']))

    def observe_travel(self,owner,origin,destination,observed_at,minutes,*,space='default',source='user_verified'):
        from .engine import WorldCoreError
        owner,space,origin,destination,source=[_valid_atom(x,'identifier') for x in (owner,space,origin,destination,source)]
        if type(minutes) not in (int,float) or not math.isfinite(minutes) or minutes<=0 or minutes>1440:raise WorldCoreError('invalid travel duration')
        with self._transaction():
            self.db.execute('INSERT INTO travel_samples VALUES (?,?,?,?,?,?,?)',
                (owner,space,origin,destination,parse_time(observed_at).isoformat(),float(minutes),source))
        return {'status':'observed'}

    def travel_forecast(self,owner,origin,destination,*,space='default',min_support=3):
        owner,space,origin,destination=[_valid_atom(x,'identifier') for x in (owner,space,origin,destination)]
        if origin==destination:return {'status':'estimated','minutes':0.,'evidence':'same_location','n':0}
        with self.lock:
            rows=self.db.execute('''SELECT minutes FROM travel_samples WHERE owner=? AND space=? AND origin=? AND destination=?
                  ORDER BY observed_at DESC LIMIT 100''',(owner,space,origin,destination)).fetchall()
        values=sorted(float(x['minutes']) for x in rows)
        if len(values)<min_support:return {'status':'abstain','reason':'no_verified_travel_history','n':len(values)}
        # Empirical 80th percentile to budget for ordinary delay; not live traffic.
        idx=math.ceil(.8*len(values))-1
        return {'status':'estimated','minutes':values[idx],'median_minutes':statistics.median(values),
                'evidence':'historical_80th_percentile_not_live_traffic','n':len(values)}

    def day_advice(self,owner,start_at,end_at,*,space='default',from_place=None,now=None):
        events=self.calendar_window(owner,start_at,end_at,space=space)
        current=parse_time(now) if now else datetime.now(timezone.utc)
        out=[]
        previous_end=current;previous_place=from_place
        for e in events:
            start=parse_time(e['start_at']);end=parse_time(e['end_at'])
            travel=(self.travel_forecast(owner,previous_place,e['place'],space=space)
                    if previous_place else {'status':'abstain','reason':'unknown_origin'})
            leaving=(start-timedelta(minutes=travel['minutes']+10) if travel.get('status')=='estimated' else None)
            out.append({'event_id':e['event_id'],'title':e['title'],'start_at':e['start_at'],
                'end_at':e['end_at'],'leave_at':leaving.isoformat() if leaving else None,
                'travel':travel,'conflict':bool(start<previous_end or (leaving and leaving<previous_end)),
                'suggestion':'Consider rescheduling' if start<previous_end or (leaving and leaving<previous_end) else 'Attend as planned',
                'no_automatic_action':True})
            previous_place=e['place'];previous_end=max(previous_end,end)
        return {'events':out,'unanswered_mail':self.mail_attention(owner,space=space,now=now),
                'limitations':'No live maps, traffic, inbox/calendar account access or autonomous bookings'}

    def optimize_stop_order(self,owner,origin,stops,*,space='default',end_at=None):
        """Exact shortest route for <=5 distinct stops with documented historical durations.

        Does not query a maps service, change appointments, or invent travel times.
        """
        from .engine import WorldCoreError
        from itertools import permutations
        owner,space,origin=[_valid_atom(x,'identifier') for x in (owner,space,origin)]
        if not isinstance(stops,list) or not 1<=len(stops)<=5 or any(not isinstance(x,str) for x in stops) or len(set(stops))!=len(stops):
            raise WorldCoreError('1..5 distinct stops required')
        for x in stops:_valid_atom(x,'identifier')
        if end_at is not None:_valid_atom(end_at,'identifier')
        solutions=[];missing=set()
        for perm in permutations(stops):
            nodes=[origin,*perm]+([end_at] if end_at else [])
            total=0.;known=True
            for a,b in zip(nodes,nodes[1:]):
                estimate=self.travel_forecast(owner,a,b,space=space)
                if estimate['status']!='estimated':
                    missing.add((a,b));known=False;break
                total+=estimate['minutes']
            if known:solutions.append((total,list(perm)))
        if not solutions:
            return {'status':'abstain','reason':'missing_empirical_route_times',
                    'unknown_legs':[list(x) for x in sorted(missing)][:20]}
        minutes,order=min(solutions)
        return {'status':'suggested','order':order,'estimated_minutes':minutes,
                'source':'observed_historical_80th_percentile','alternatives_considered':len(solutions),
                'limitations':'No live traffic; no travel mode or real-world map API; user must approve changes'}

    def recommend_slot(self,owner,window_start,window_end,duration_minutes,*,space='default',place='remote',from_place=None,step_minutes=15):
        from .engine import WorldCoreError
        a,b=parse_time(window_start),parse_time(window_end)
        if not isinstance(duration_minutes,int) or duration_minutes not in range(5,481):raise WorldCoreError('invalid duration')
        if b<=a or b-a>timedelta(days=7):raise WorldCoreError('invalid time window')
        if not isinstance(step_minutes,int) or step_minutes not in range(5,61):raise WorldCoreError('invalid step')
        events=self.calendar_window(owner,(a-timedelta(days=1)).isoformat(),(b+timedelta(days=1)).isoformat(),space=space)
        candidates=[]; t=a
        while t+timedelta(minutes=duration_minutes)<=b:
            end=t+timedelta(minutes=duration_minutes)
            if not any(t<parse_time(e['end_at']) and end>parse_time(e['start_at']) for e in events):
                prior=[e for e in events if parse_time(e['end_at'])<=t]
                nxt=[e for e in events if parse_time(e['start_at'])>=end]
                before=prior[-1] if prior else None;after=nxt[0] if nxt else None
                origin=before['place'] if before else from_place
                scores=[];feasible=True
                for o,d,available in [
                    (origin,place,(t-parse_time(before['end_at'])).total_seconds()/60 if before else None),
                    (place,after['place'] if after else None,(parse_time(after['start_at'])-end).total_seconds()/60 if after else None)]:
                    if not o or not d:continue
                    travel=self.travel_forecast(owner,o,d,space=space)
                    if travel['status']!='estimated':feasible=False;break
                    if available is not None and travel['minutes']+10>available:feasible=False;break
                    scores.append(travel['minutes'])
                if feasible:
                    candidates.append({'start':t.isoformat(),'end':end.isoformat(),'travel_minutes_known':sum(scores),
                                       'score':sum(scores)+abs(t.hour-10)*.01,'status':'feasible_from_known_data'})
            t+=timedelta(minutes=step_minutes)
        if not candidates:return {'status':'abstain','reason':'no_verified_feasible_slot','checked':True}
        best=min(candidates,key=lambda x:x['score'])
        return {'status':'suggested','best':best,'alternatives':sorted(candidates,key=lambda x:x['score'])[1:4],
                'limitations':'No automatic calendar changes; availability limited to ingested events; no live travel times'}
