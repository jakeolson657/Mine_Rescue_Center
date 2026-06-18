"""Export a CalendarEvent to other calendar apps.

Events are all-day (DateField start/end), so the iCalendar output uses
``VALUE=DATE`` values and an *exclusive* ``DTEND`` (the day after the last day),
which is what the spec and every calendar app expect for all-day spans. The
same exclusive-end convention is used for the Google and Outlook "add event"
deep links so a one-day contest shows as one day everywhere.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode


def _ics_escape(text):
    """Escape a value for an iCalendar property (RFC 5545 §3.3.11)."""
    return (
        str(text)
        .replace('\\', '\\\\')
        .replace(';', '\\;')
        .replace(',', '\\,')
        .replace('\r\n', '\\n')
        .replace('\r', '\\n')
        .replace('\n', '\\n')
    )


def _fold(line):
    """Fold a content line to <=75 octets (RFC 5545 §3.1) without splitting a
    multi-byte UTF-8 character. Continuation lines begin with a single space."""
    raw = line.encode('utf-8')
    if len(raw) <= 75:
        return line
    chunks, start, limit = [], 0, 75
    while start < len(raw):
        end = min(start + limit, len(raw))
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:  # mid-character byte
            end -= 1
        chunks.append(raw[start:end])
        start, limit = end, 74  # continuation lines carry a leading space
    return '\r\n '.join(chunk.decode('utf-8') for chunk in chunks)


def _description(event, url=None):
    """Human-readable body shared by the .ics file and the deep links."""
    parts = []
    if event.description:
        parts.append(event.description.strip())
    if event.contact_info:
        parts.append(f"Contact: {event.contact_info.strip()}")
    if url:
        parts.append(url)
    return "\n\n".join(parts)


def build_event_ics(event, url=None, now=None):
    """Return an iCalendar document (CRLF line endings) for a single event."""
    now = now or datetime.now(timezone.utc)
    start = event.start_date.strftime('%Y%m%d')
    end = (event.end_date + timedelta(days=1)).strftime('%Y%m%d')
    description = _description(event, url)

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Mine Rescue Center//Competition Calendar//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:event-{event.pk}@minerescuecenter.com',
        f'DTSTAMP:{now.strftime("%Y%m%dT%H%M%SZ")}',
        f'DTSTART;VALUE=DATE:{start}',
        f'DTEND;VALUE=DATE:{end}',
        f'SUMMARY:{_ics_escape(event.title)}',
    ]
    if event.location:
        lines.append(f'LOCATION:{_ics_escape(event.location)}')
    if description:
        lines.append(f'DESCRIPTION:{_ics_escape(description)}')
    if url:
        lines.append(f'URL:{_ics_escape(url)}')
    lines += ['END:VEVENT', 'END:VCALENDAR']

    return '\r\n'.join(_fold(line) for line in lines) + '\r\n'


def google_calendar_url(event, url=None):
    """"Add to Google Calendar" deep link."""
    start = event.start_date.strftime('%Y%m%d')
    end = (event.end_date + timedelta(days=1)).strftime('%Y%m%d')
    params = {
        'action': 'TEMPLATE',
        'text': event.title,
        'dates': f'{start}/{end}',
    }
    details = _description(event, url)
    if details:
        params['details'] = details
    if event.location:
        params['location'] = event.location
    return 'https://calendar.google.com/calendar/render?' + urlencode(params)


def outlook_calendar_url(event, url=None):
    """"Add to Outlook.com calendar" deep link (the compose form)."""
    params = {
        'rru': 'addevent',
        'subject': event.title,
        'startdt': event.start_date.strftime('%Y-%m-%d'),
        'enddt': (event.end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
        'allday': 'true',
    }
    body = _description(event, url)
    if body:
        params['body'] = body
    if event.location:
        params['location'] = event.location
    return 'https://outlook.live.com/calendar/0/action/compose?' + urlencode(params)
