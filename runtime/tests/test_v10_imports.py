import pytest
from worldcore import WorldCore,WorldCoreError
from worldcore.personal_imports import parse_calendar_ics,parse_eml_header_metadata

ICS='''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:e1
SUMMARY:Appuntamento
DTSTART;TZID=Europe/Rome:20261030T093000
DTEND;TZID=Europe/Rome:20261030T103000
LOCATION:office
END:VEVENT
END:VCALENDAR'''

def test_ical_timezone_and_consent(tmp_path):
    r=parse_calendar_ics(ICS)
    assert r['events'][0]['start_at']=='2026-10-30T08:30:00+00:00'
    with WorldCore(tmp_path/'db') as core:
        with pytest.raises(WorldCoreError):core.import_calendar_ics('u',ICS)
        r=core.import_calendar_ics('u',ICS,consent=True)
        assert r['count']==1
        assert len(core.calendar_window('u','2026-10-30T08:00:00Z','2026-10-30T11:00:00Z'))==1

def test_recurrence_is_not_silently_expanded():
    doc=parse_calendar_ics(ICS.replace('END:VEVENT','RRULE:FREQ=DAILY;COUNT=20\nEND:VEVENT'))
    assert 'recurrence_not_expanded' in doc['warnings']

def test_ics_floating_time_rejected():
    with pytest.raises(WorldCoreError):parse_calendar_ics(ICS.replace('DTSTART;TZID=Europe/Rome:','DTSTART:'))

def test_eml_only_metadata(tmp_path):
    data=b'From: Alice <alice@example.com>\r\nTo: Bob <bob@example.com>\r\nSubject: Please confirm\r\nMessage-ID: <foo@example.com>\r\nDate: Fri, 30 Oct 2026 09:30:00 +0100\r\n\r\nSecret body content\r\n'
    doc=parse_eml_header_metadata(data)
    assert 'Secret body' not in str(doc) and 'alice@example.com' not in str(doc)
    with WorldCore(tmp_path/'db') as core:
        with pytest.raises(WorldCoreError):core.import_eml_metadata('u',data)
        core.import_eml_metadata('u',data,consent=True,requires_reply=True)
        assert 'Please confirm' in core.mail_attention('u',now='2026-10-30T10:00:00Z')[0]['subject']
