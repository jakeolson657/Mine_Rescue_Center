"""Programmatically-built quizzes for TEXT-layer tests whose answer format the
main extractor doesn't handle: filled-bullet answer keys ("• C.") and split
Day-1/Day-2 letter keys. Imported by build_manual.py; each entry is a manual
quiz on the test's own source_document."""
import os, re
import fitz
from django.conf import settings
from pages.models import ProblemDocument
import extractor


def _text(pk):
    d = ProblemDocument.objects.get(pk=pk)
    doc = fitz.open(os.path.join(settings.MEDIA_ROOT, d.file.name))
    return '\n'.join(p.get_text() for p in doc)


_CH = re.compile(r'^\s*([•●■‣oO○°*]?)\s*([A-Ea-e])[\.\)]\s*(.*)$')
_QN = re.compile(r'^\s*(\d{1,2})[\.\)]')
_FILLED = '•●■‣'  # bullet / black circle / black square / triangle bullet


def parse_bullet(pk):
    """Answer doc where the correct choice is marked with a FILLED bullet
    ('• C. harmless') and the others with an empty one ('o A. ...')."""
    lines = [l.rstrip() for l in _text(pk).split('\n')]
    qs, cur = [], None
    for l in lines:
        s = l.strip()
        if not s:
            continue
        m = _CH.match(s)
        if m and cur is not None and len(cur['choices']) < 5 and m.group(2).upper() == 'ABCDE'[len(cur['choices'])]:
            cur['choices'].append({'text': m.group(3).strip(), 'is_correct': m.group(1) in _FILLED})
            continue
        qm = _QN.match(s)
        if qm and (cur is None or len(cur['choices']) >= 2):
            if cur:
                qs.append(cur)
            cur = {'text': s[qm.end():].strip().lstrip(')').strip(), 'choices': []}
            continue
        if cur is not None:
            if cur['choices']:
                cur['choices'][-1]['text'] += ' ' + s
            else:
                cur['text'] += ' ' + s
    if cur:
        qs.append(cur)
    # keep only well-formed single-correct questions
    return [q for q in qs if len(q['choices']) >= 2 and sum(c['is_correct'] for c in q['choices']) == 1]


def build_from_letter_key(test_pk, key, max_pages=None):
    """Extract the (labeled a/b/c) questions from a clean test doc and mark the
    correct choice from a {question_number: letter} answer key."""
    d = ProblemDocument.objects.get(pk=test_pk)
    raw = extractor.extract_questions(os.path.join(settings.MEDIA_ROOT, d.file.name), max_pages=max_pages)[0]
    out = []
    for q in raw:
        n = q.get('number')
        if n not in key:
            continue
        ch = [extractor.clean_text(c['raw']) for c in q['choices'] if extractor.clean_text(c['raw']).strip()]
        idx = 'ABCDE'.index(key[n])
        if len(ch) < 2 or idx >= len(ch):
            continue
        out.append({'text': extractor.clean_text(q['text']),
                    'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(ch)]})
    return out


# 2022 Fallen Heroes Day 1 / Day 2 (pk191 / pk192); the shared answer key pk193
# lists both days interleaved ("1.(04)A" Day1, "1.(52)C" Day2) — split here.
_FH_D1 = {1: 'A', 2: 'B', 3: 'A', 4: 'C', 5: 'C', 6: 'B', 7: 'B', 8: 'C', 9: 'C', 10: 'A'}
_FH_D2 = {1: 'C', 2: 'B', 3: 'B', 4: 'C', 5: 'C', 6: 'B', 7: 'A', 8: 'C', 9: 'C', 10: 'C'}

TEXT_QUIZZES = [
    # 2024 Colorado Regional (RMMRC Preshift) written test pk72; answers in pk73.
    {'source_pk': 72, 'title': 'Written Test', 'questions': parse_bullet(73)},
    {'source_pk': 191, 'title': 'Day 1 Written Test', 'questions': build_from_letter_key(191, _FH_D1)},
    {'source_pk': 192, 'title': 'Day 2 Written Test', 'questions': build_from_letter_key(192, _FH_D2)},
]
