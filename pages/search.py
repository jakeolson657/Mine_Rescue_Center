"""Competition search for the calendar page: match events by name or place.

Every word typed has to match somewhere in the event's title, its location,
or the name of a competition linked to it. State names also match the
two-letter abbreviation locations use ("kentucky" finds "Lexington, KY").
"""
import re

from django.db.models import Q
from django.utils import timezone

from .models import US_STATES, CalendarEvent, short_location

_ABBR_TO_NAME = {abbr: name for name, abbr in US_STATES.items()}
# Longest names first so "west virginia" wins over "virginia".
_STATE_NAMES = sorted(US_STATES, key=len, reverse=True)


def state_name(location):
    """Spelled-out state for a venue ("Lexington, KY" -> "Kentucky"), or ''.
    Lets the past-problems search find a contest by its state's name."""
    label = short_location(location)
    abbr = label.rsplit(', ', 1)[-1] if ', ' in label else ''
    return _ABBR_TO_NAME.get(abbr, '').title()


def _state_q(name, abbr):
    return (Q(title__icontains=name) | Q(location__icontains=name)
            | Q(location__iregex=rf',\s*{abbr}(\s|$|[0-9])'))


def _query_filters(query):
    """Split ``query`` into one Q per word (or state name) that must all match."""
    text = ' '.join(re.findall(r"[\w'&/.-]+", query))
    filters = []
    for name in _STATE_NAMES:
        pattern = rf'\b{re.escape(name)}\b'
        if re.search(pattern, text, re.IGNORECASE):
            filters.append(_state_q(name, US_STATES[name]))
            text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
    words = text.split()
    for word in words:
        # "2026 harlan": a year matches events held that year.
        if re.fullmatch(r'(19|20)\d\d', word):
            year = int(word)
            filters.append(Q(start_date__year=year) | Q(end_date__year=year)
                           | Q(competitions__year=year))
            continue
        # "WV" (or a lone "wv") is a state; a lowercase "in" or "or" in a
        # longer search is just a word.
        if word.upper() in _ABBR_TO_NAME and (word.isupper() or len(words) == 1):
            filters.append(_state_q(_ABBR_TO_NAME[word.upper()], word.upper()))
            continue
        # "nationals" should find "National Mine Rescue Contest".
        if len(word) > 4 and word.lower().endswith('s'):
            word = word[:-1]
        filters.append(Q(title__icontains=word) | Q(location__icontains=word)
                       | Q(competitions__name__icontains=word))
    return filters


def search_events(query, limit=None):
    """Events matching ``query``: upcoming ones first (soonest first), then
    past ones (most recent first). Returns ``(results, total)`` where each
    result is the event with ``place`` and ``upcoming`` set."""
    filters = _query_filters(query or '')
    if not filters:
        return [], 0
    events = CalendarEvent.objects.all()
    for f in filters:
        events = events.filter(f)
    events = list(events.distinct())

    today = timezone.localdate()
    upcoming = sorted((e for e in events if e.end_date >= today),
                      key=lambda e: e.start_date)
    past = sorted((e for e in events if e.end_date < today),
                  key=lambda e: e.start_date, reverse=True)
    results = upcoming + past
    for event in results:
        event.place = short_location(event.location)
        event.upcoming = event.end_date >= today
    total = len(results)
    return (results[:limit] if limit else results), total
