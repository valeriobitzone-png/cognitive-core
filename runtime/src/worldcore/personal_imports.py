"""Explicit, offline import of authorized .ics and .eml metadata.

Limited ICS VEVENT subset; recurring rules and complex timezone definitions are NOT
expanded. For production use a standards-compliant calendar provider connector.
Never connects to an account, sends mail or retains email bodies/attachments.
"""
from __future__ import annotations
import hashlib
from datetime import datetime,timedelta,timezone
from email import policy
from email.parser import BytesParser
from email.header import decode_header,make_header
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from .engine import WorldCoreError


def _ical_date(modifier,raw):
    if not raw or len(raw)>48:raise WorldCoreError('missing or invalid ICS date')
    try:
        if modifier.get('VALUE')=='DATE' or (len(raw)==8 and raw.isdigit()):
            dt=datetime.strptime(raw,'%Y%m%d').replace(tzinfo=timezone.utc)
            return dt,True
        if raw.endswith('Z'):
            return datetime.strptime(raw,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc),False
        tzid=modifier.get('TZID')
        if not tzid:raise WorldCoreError('floating ICS times need an explicit TZID')
        dt=datetime.strptime(raw,'%Y%m%dT%H%M%S')
        return dt.replace(tzinfo=ZoneInfo(tzid)).astimezone(timezone.utc),False
    except (ValueError,ZoneInfoNotFoundError) as exc:raise WorldCoreError('unsupported ICS timestamp') from exc

def parse_calendar_ics(data):
    if isinstance(data,bytes):
        if len(data)>1_000_000:raise WorldCoreError('ICS content too large')
        data=data.decode('utf-8')
    if not isinstance(data,str) or len(data)>1_000_000:raise WorldCoreError('invalid ICS data')
    rows=[]
    for line in data.replace('\r\n','\n').split('\n'):
        if line.startswith((' ','\t')) and rows:rows[-1]+=line[1:]
        else:rows.append(line)
    events=[];current=None;warnings=[]
    for line in rows:
        if line=='BEGIN:VEVENT':
            current={};continue
        if line=='END:VEVENT':
            if current is None:continue
            if 'RRULE' in current: warnings.append('recurrence_not_expanded')
            if not all(k in current for k in ('UID','SUMMARY','DTSTART')):
                warnings.append('incomplete_event_skipped');current=None;continue
            begin,all_day=_ical_date(*current['DTSTART'])
            if 'DTEND' in current:finish,_=_ical_date(*current['DTEND'])
            elif all_day:finish=begin+timedelta(days=1)
            else:warnings.append('missing_end_skipped');current=None;continue
            if finish<=begin:
                warnings.append('bad_duration_skipped');current=None;continue
            events.append({'event_id':current['UID'][1][:128], 'title':current['SUMMARY'][1][:240],
                'start_at':begin.isoformat(),'end_at':finish.isoformat(),
                'place':current.get('LOCATION',({},'remote'))[1][:128] or 'remote',
                'status':current.get('STATUS',({},'CONFIRMED'))[1].lower()})
            current=None;continue
        if current is not None and ':' in line:
            key,value=line.split(':',1);segments=key.split(';');name=segments[0].upper();params={}
            for segment in segments[1:]:
                if '=' in segment:
                    k,v=segment.split('=',1);params[k.upper()]=v.strip('"')
            if name in ('UID','SUMMARY','DTSTART','DTEND','LOCATION','STATUS','RRULE'):
                current[name]=(params,value.replace('\\,',',').replace('\\n','\n'))
    return {'events':events,'warnings':sorted(set(warnings)),
            'limitations':'subset of VEVENT only; no recurrence expansion or VTIMEZONE definitions'}

def parse_eml_header_metadata(blob):
    if not isinstance(blob,bytes) or len(blob)>2_000_000:raise WorldCoreError('invalid EML bytes')
    msg=BytesParser(policy=policy.default).parsebytes(blob,headersonly=True)
    rawdate=msg.get('Date')
    if not rawdate:raise WorldCoreError('message Date header required')
    try:stamp=parsedate_to_datetime(str(rawdate))
    except (ValueError,TypeError) as exc:raise WorldCoreError('invalid email Date') from exc
    if stamp.tzinfo is None:raise WorldCoreError('email timezone required')
    subject=str(msg.get('Subject','')).strip()[:240] or '(no subject)'
    msgid=str(msg.get('Message-ID','')).strip()
    token=hashlib.sha256((msgid or subject+stamp.isoformat()).encode()).hexdigest()[:32]
    return {'signal_id':'eml:'+token,'received_at':stamp.astimezone(timezone.utc).isoformat(),
            'subject':subject,'stored_metadata_only':True,'limitations':'no body, attachments, sender or recipient read'}
