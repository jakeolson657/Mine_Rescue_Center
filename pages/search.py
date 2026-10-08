"""Competition search for the calendar page: match events by name, place,
year, or a specific file.

Every word typed has to match somewhere in the event's title, its location,
or the name of a competition linked to it. State names also match the
two-letter abbreviation locations use ("kentucky" finds "Lexington, KY"), and
a year ("2026 harlan") matches events held that year.

When the words only fit once a file's name is counted ("2026 trainer test"),
the event is still returned but narrowed to those files: the posted problem
documents and the event's own links (results, flyers, registration forms).
This mirrors the archive search on the past-problems page.
"""
import re

from django.db.models import Prefetch
from django.utils import timezone

from .models import (
    US_STATES, CalendarEvent, Competition, CompetitionProblem, short_location,
)

_ABBR_TO_NAME = {abbr: name for name, abbr in US_STATES.items()}
# Longest names first so "west virginia" wins over "virginia".
_STATE_NAMES = sorted(US_STATES, key=len, reverse=True)


def state_name(location):
    """Spelled-out state for a venue ("Lexington, KY" -> "Kentucky"), or ''.
    Lets the past-problems search find a contest by its state's name."""
    label = short_location(location)
    abbr = label.rsplit(', ', 1)[-1] if ', ' in label else ''
    return _ABBR_TO_NAME.get(abbr, '').title()


def _terms(query):
    """Split ``query`` into terms that must all match: ('state', name, abbr),
    ('year', 2026) or ('word', text)."""
    text = ' '.join(re.findall(r"[\w'&/.-]+", query or ''))
    terms = []
    for name in _STATE_NAMES:
        pattern = rf'\b{re.escape(name)}\b'
        if re.search(pattern, text, re.IGNORECASE):
            terms.append(('state', name, US_STATES[name]))
            text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
    words = text.split()
    for word in words:
        if re.fullmatch(r'(19|20)\d\d', word):
            terms.append(('year', int(word)))
        # "WV" (or a lone "wv") is a state; a lowercase "in" or "or" in a
        # longer search is just a word.
        elif word.upper() in _ABBR_TO_NAME and (word.isupper() or len(words) == 1):
            abbr = word.upper()
            terms.append(('state', _ABBR_TO_NAME[abbr], abbr))
        else:
            # "nationals" should find "National Mine Rescue Contest".
            if len(word) > 4 and word.lower().endswith('s'):
                word = word[:-1]
            terms.append(('word', word.lower()))
    return terms


def _matches(term, text, event):
    """Does ``term`` match ``text`` (lowercased) for ``event``?"""
    kind = term[0]
    if kind == 'year':
        return term[1] in event.search_years
    if kind == 'state':
        return (term[1] in text
                or re.search(rf',\s*{term[2]}(\s|$|[0-9])', event.location, re.IGNORECASE))
    return term[1] in text


def _all_match(terms, text, event):
    return all(_matches(t, text, event) for t in terms)


def _files(event):
    """(search text, file dict) for each file attached to ``event``."""
    for resource in event.resources or []:
        label = resource.get('label') or ''
        if resource.get('url'):
            yield label.lower(), {'label': label, 'url': resource['url'], 'context': 'Link'}
    for competition in event.competitions.all():
        for problem in competition.problems.all():
            for doc in problem.documents.all():
                yield (f'{problem.title} {doc.title}'.lower(),
                       {'label': doc.title, 'url': doc.file.url, 'context': problem.title})


def search_events(query, limit=None):
    """Events matching ``query``: upcoming ones first (soonest first), then
    past ones (most recent first). Returns ``(results, total)``; each result
    is the event with ``place``, ``upcoming`` and ``matched_files`` set
    (``matched_files`` is empty unless the search picked out specific files)."""
    terms = _terms(query)
    if not terms:
        return [], 0

    events = CalendarEvent.objects.prefetch_related(Prefetch(
        'competitions',
        queryset=Competition.objects.prefetch_related(Prefetch(
            'problems',
            queryset=CompetitionProblem.objects.prefetch_related('documents'),
        )),
    ))

    matched = []
    for event in events:
        competitions = list(event.competitions.all())
        event.search_years = {event.start_date.year, event.end_date.year}
        event.search_years.update(c.year for c in competitions if c.year)
        base = ' '.join([event.title, event.location]
                        + [c.name for c in competitions]).lower()
        event.matched_files = []
        if _all_match(terms, base, event):
            matched.append(event)
            continue
        event.matched_files = [
            info for text, info in _files(event)
            if _all_match(terms, f'{base} {text}', event)
        ]
        if event.matched_files:
            matched.append(event)

    today = timezone.localdate()
    upcoming = sorted((e for e in matched if e.end_date >= today),
                      key=lambda e: e.start_date)
    past = sorted((e for e in matched if e.end_date < today),
                  key=lambda e: e.start_date, reverse=True)
    results = upcoming + past
    for event in results:
        event.place = short_location(event.location)
        event.upcoming = event.end_date >= today
    total = len(results)
    return (results[:limit] if limit else results), total
