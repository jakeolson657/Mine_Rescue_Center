"""General written-test -> quiz extractor. Captures question/choice structure
with per-choice metadata (text color, bold, highlight rect, trailing citation)
and tries multiple answer-marking conventions, keeping whichever makes every
question have exactly one correct choice.

Answer-marking conventions handled:
  - highlight rect behind the correct choice (any distinct fill color)
  - correct choice TEXT colored (e.g. red) different from the others
  - correct choice bold
  - correct choice annotated with a trailing "(... page N)" source citation
  - separate numbered "N. <answer>" answer-list doc matched back to choices
  - answers marked in mixed shades (grouped via anycolor/anyhighlight detectors)
  - a clean MC section followed by an un-quizzable tail (image-based parts ID,
    or a printed answer-key list) -> keep the clean leading run only

Always validates before returning clean=True. Citations are stripped from the
stored choice text so the answer is never given away.
"""
import os
import re
import fitz  # pymupdf
import pypdf

CHOICE_RE = re.compile(r'^\(?([a-eA-E])[\.\)]\s*(.+)$')
# a choice letter alone on its own line ("a." / "b)"), with the choice text on
# the following line(s)
LONE_CHOICE_RE = re.compile(r'^\(?([a-eA-E])[\.\)]\s*$')
# Number then a RUN of ./) separators so a "1.)" style stem doesn't leave a
# stray ")" glued to the question text ("1.)  Normal air…" -> "Normal air…").
QNUM_RE = re.compile(r'^\(?(\d{1,2})[\.\)]+\s*(.*)$')
# "Q#1)" question marker (the stem usually follows on the next line). Used by the
# Southern/Southwest Regional template whose answers are an "A#N)" key.
QHASH_RE = re.compile(r'^\s*Q\s*#\s*(\d{1,2})\)\s*(.*)$', re.I)
STAR_MARK_RE = re.compile(r'\*+\s*$')
REF_KW = r'(?:page|pg|module|manual|section|ig\b|msha|appendix)'
# any trailing bracketed/paren reference — used as the "this choice is cited" signal
CITATION_RE = re.compile(r'[\(\[][^\[\]]*(?:\d|page|pg|module|manual|section|msha|ig)\b', re.I)
# trailing [ ... ref ... ] (inner may contain parens), e.g. [MSHA 3027 (IG6), pg.2-6]
BRACKET_RE = re.compile(r'\s*\[[^\[\]]*(?:\d|' + REF_KW + r')[^\[\]]*\]\s*$', re.I)
# trailing ( ... ref ... ), one level of nested parens tolerated
PAREN_RE = re.compile(r'\s*\((?:[^()]|\([^()]*\))*\b' + REF_KW + r'\b(?:[^()]|\([^()]*\))*\)\s*$', re.I)
# trailing bare reference tail anchored on Module/Page/Pg followed by a digit,
# tolerating dash/asterisk/odd separators: "Module 2-page12", "Module 2�page 43",
# "Page 2 of 6", "--- Module 2-page12".
MODULE_RE = re.compile(r'\s*[-*\s]*(?:Module\b[\s#.\W]*\d+[\s\W]*)?(?:page|pg)[\s#.\W]*\d[\d\-\s]*(?:of\s*\d+)?\s*$', re.I)
# trailing lone marker asterisk(s)
STAR_RE = re.compile(r'\s*\*+\s*$')
# trailing question-bank reference tag like "(#75)" or a paren-stripped "(#75"
REFTAG_RE = re.compile(r'\s*\(#\s*\d+\)?\s*$')
# key/answer separator decorations ("///// KEY \\\\\") and everything after them
SEP_RE = re.compile(r'\s*[/\\]{3,}.*$', re.S)
# page footer artifacts bled in at a page break: "4 | P a g e", "Page 4 of 6",
# and a "... MERD- Mine Rescue Exam 4 | Page"-style running footer.
FOOTER_RE = re.compile(r'\s*(?:\d+\s*\|\s*)?P\s*a\s*g\s*e(?:\s*\d+(?:\s*of\s*\d+)?)?\s*$', re.I)
FOOTER2_RE = re.compile(r'\s*\bPage\s*\d+\s*of\s*\d+\s*$', re.I)
# Trailing source citation/rationale not in brackets, e.g. "—page 16,17",
# "– Brady 9th, page 89, question 4", " page 2-7, <explanation>", "answer in
# operation guide on iTX page 3". Anchored on a reference keyword so ordinary
# answer text is left intact.
TAIL_CITE_RE = re.compile(
    r'[\s—–,;(]*(?:'
    r'\b(?:pages?|pg|modules?|chapters?|sections?)\b\.?\s*#?\s*\d'
    r'|\bbrady\b'
    r'|\banswer\s+in\b'
    r'|\bsee\s+(?:page|pg|module|section|the)\b'
    r').*$', re.I)
# A trailing dash-separated citation ("– 30CFR 49.15(d)", "– 2014 MNM Contest
# Rules") — only when the segment after the dash carries a citation signal, so
# numeric ranges ("60 – 100", "1.9 – 2.5") and hyphenated words ("By-Pass") stay.
DASH_CITE_RE = re.compile(
    r'\s*[—–]\s*(?=[^—–]*(?:cfr|\brules?\b|\bpages?\b|\bpg\b|\bmodules?\b'
    r'|\bsections?\b|\bbrady\b|\bcontest\b|guidelines))(?:[^—–]*[—–]?)*$', re.I)
BOLD_FLAG = 1 << 4

# A source-citation signal inside a trailing parenthetical: page/section refs,
# rule/standard cites, textbook names, etc. Answer keys often append these to the
# CORRECT choice ("Undercast (2012 Contest Rules, p114)", "(brady p. 596)"),
# which both gives the answer away and reads as noise, so they must be stripped.
CITE_SIGNAL = re.compile(
    r'\bpp?\.?\s*\d|\bpages?\b|\bpg\b|\brules?\b|cfr|\bc\.?f\.?r\b|\bpart\s*\d'
    r'|\bbrady\b|\bchapters?\b|\bmodules?\b|\bsections?\b|\bmanuals?\b|\bappendix\b'
    r'|\big\b|\bnoaa\b|\bnws\b|\bhandbooks?\b|\bpub\b|¶', re.I)


def _strip_citation_tail(t):
    """Remove a trailing source citation in parentheses, whether balanced
    ("(p. 2-21)") or truncated/unbalanced ("(2012 Contest Rules, p114"), but only
    when it carries a citation signal — legitimate parentheticals like "(CH4)",
    "(H2S)" or "(b)" are left alone."""
    # unbalanced trailing '(' — cut from the last unmatched '('
    depth, cut = 0, None
    for i, ch in enumerate(t):
        if ch == '(':
            if depth == 0:
                cut = i
            depth += 1
        elif ch == ')' and depth > 0:
            depth -= 1
            if depth == 0:
                cut = None
    if depth > 0 and cut is not None and CITE_SIGNAL.search(t[cut:]):
        return t[:cut].strip()
    # balanced trailing (...) citation
    m = re.search(r'\s*\((?:[^()]|\([^()]*\))*\)\s*$', t)
    if m and CITE_SIGNAL.search(m.group(0)):
        return t[:m.start()].strip()
    return t


def _strip_trailing(t, rx):
    """Strip a trailing citation match, but only when it starts after position 0.
    A real trailing citation always has answer/stem text before it; when the whole
    string matches (start == 0) the text IS a citation-shaped phrase — e.g. a
    question stem "Section 7(3) of the MINER Act…" — and must be kept, not eaten."""
    m = rx.search(t)
    if m and m.start() > 0:
        return t[:m.start()].strip()
    return t


def clean_text(t):
    prev = None
    while prev != t:
        prev = t
        t = SEP_RE.sub('', t).strip()          # "///// KEY \\\\\ …" and trailing junk
        t = FOOTER2_RE.sub('', t).strip()      # "Page 4 of 6"
        t = FOOTER_RE.sub('', t).strip()       # "4 | P a g e"
        t = BRACKET_RE.sub('', t).strip()
        t = PAREN_RE.sub('', t).strip()
        t = _strip_trailing(t, TAIL_CITE_RE)
        t = DASH_CITE_RE.sub('', t).strip()
        t = _strip_citation_tail(t)
        t = MODULE_RE.sub('', t).strip()
        t = STAR_RE.sub('', t).strip()
        t = REFTAG_RE.sub('', t).strip()
    return t.rstrip('.,]-* ').strip()


def _is_neutral(color_int):
    # color as packed int 0xRRGGBB
    r = (color_int >> 16) & 255
    g = (color_int >> 8) & 255
    b = color_int & 255
    if r > 220 and g > 220 and b > 220:
        return True
    if r < 40 and g < 40 and b < 40:
        return True
    return False


def _highlight_rects_by_color(page):
    by_color = {}
    pw = page.rect.width
    for d in page.get_drawings():
        fill = d.get('fill')
        if d.get('type') not in ('f', 'fs') or fill is None:
            continue
        r, g, b = [int(round(c * 255)) for c in fill]
        packed = (r << 16) | (g << 8) | b
        if _is_neutral(packed):
            continue
        rect = d['rect']
        if rect.width > pw * 0.7:
            continue
        by_color.setdefault(packed, []).append(rect)
    return by_color


def _split_multichoice(spans, rect, pi):
    """If a single line packs several choices ("A. 10   B. 5   C. 15"), return a
    list of choice dicts (with per-choice color/star mapped from the character
    ranges), else None. Handles the common preshift/True-False layout where all
    options sit on one line."""
    text = ''
    colors, flags, xs = [], [], []   # xs: approximate x-center of each character
    for s in spans:
        t = s['text']
        text += t
        colors.extend([s['color']] * len(t))
        flags.extend([s['flags']] * len(t))
        x0, x1 = s['bbox'][0], s['bbox'][2]
        n = max(len(t), 1)
        xs.extend(x0 + (x1 - x0) * ((i + 0.5) / n) for i in range(len(t)))
    # A choice marker is a letter then "." / ")", OR (OCR dropped the dot) a bare
    # letter followed by a capitalized word — but only accepted as a marker when
    # the letters still read as a clean a,b,c… run, so a stray "A Positive" in a
    # stem doesn't trigger a split.
    markers = list(re.finditer(r'(?:^|\s)\(?([a-eA-E])(?:[\.\)]|(?=\s+[A-Z0-9]))', text))
    if len(markers) < 2:
        return None
    letters = [m.group(1).lower() for m in markers]
    if letters != [chr(ord('a') + i) for i in range(len(letters))]:
        return None  # must be sequential a,b,c… to be a real choice row
    out = []
    for i, m in enumerate(markers):
        s0 = m.end()
        s1 = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        seg = text[s0:s1]
        seg_colors = [c for c in colors[s0:s1] if c and not _is_neutral(c)]
        seg_xs = xs[m.start():s1]  # include the "c." marker so a highlight that
        out.append({                # starts at the letter still overlaps the choice
            'raw': seg.strip(),
            'color': seg_colors[0] if seg_colors else None,
            'bold': any(f & BOLD_FLAG for f in flags[s0:s1]),
            'citation': bool(CITATION_RE.search(seg)),
            'star': bool(STAR_MARK_RE.search(seg)),
            'y0': rect.y0, 'y1': rect.y1, 'page': pi,
            'x0': min(seg_xs) if seg_xs else rect.x0, 'x1': max(seg_xs) if seg_xs else rect.x1,
        })
    return out


def extract_questions(pdf_path, max_pages=None):
    """Return (questions, highlight_map). Each question:
      {'text', 'choices': [{'text','raw','color','bold','citation','y0','y1','page'}]}
    highlight_map: {page_index: {color_int: [rects]}}.
    max_pages limits how many leading pages are read (used to stop before a
    diagram-based parts section that would otherwise bleed into the last
    multiple-choice question)."""
    doc = fitz.open(pdf_path)
    questions = []
    current = None
    highlight_map = {}

    for pi, page in enumerate(doc):
        if max_pages is not None and pi >= max_pages:
            break
        highlight_map[pi] = _highlight_rects_by_color(page)
        d = page.get_text('dict')
        for block in d['blocks']:
            for line in block.get('lines', []):
                spans = [s for s in line.get('spans', []) if s['text'].strip()]
                if not spans:
                    continue
                text = ''.join(s['text'] for s in spans).strip()
                rect = fitz.Rect(line['bbox'])
                qm = QNUM_RE.match(text)
                qh = QHASH_RE.match(text)
                cm = CHOICE_RE.match(text)
                lone = LONE_CHOICE_RE.match(text)
                colors = [s['color'] for s in spans if s['color'] and not _is_neutral(s['color'])]
                bold = any(s['flags'] & BOLD_FLAG for s in spans)
                multi = None if ((qm or qh) and not cm) else _split_multichoice(spans, rect, pi)
                # "Q#1)" marker — the stem follows on the next line(s), picked up by
                # the continuation branch below (choices are still empty).
                if qh and not cm:
                    if current:
                        questions.append(current)
                    current = {'number': int(qh.group(1)), 'text': qh.group(2), 'choices': []}
                    continue
                if qm and not cm and not lone and not multi:
                    if current:
                        questions.append(current)
                    current = {'number': int(qm.group(1)), 'text': qm.group(2), 'choices': []}
                    continue
                if multi and current is not None:
                    current['choices'].extend(multi)
                    continue
                if (cm or lone) and current is not None:
                    body = cm.group(2).strip() if cm else ''
                    current['choices'].append({
                        'raw': body,
                        'color': colors[0] if colors else None,
                        'bold': bold,
                        'citation': bool(CITATION_RE.search(text)),
                        'star': bool(STAR_MARK_RE.search(text)),
                        'y0': rect.y0, 'y1': rect.y1, 'page': pi,
                        'x0': rect.x0, 'x1': rect.x1,   # one choice per line: full width
                    })
                    continue
                # continuation line
                if current is not None:
                    if current['choices']:
                        ch = current['choices'][-1]
                        ch['raw'] = (ch['raw'] + ' ' + text).strip()
                        if CITATION_RE.search(text):
                            ch['citation'] = True
                        if STAR_MARK_RE.search(text):
                            ch['star'] = True
                        for s in spans:
                            if s['color'] and not _is_neutral(s['color']) and ch['color'] is None:
                                ch['color'] = s['color']
                            if s['flags'] & BOLD_FLAG:
                                ch['bold'] = True
                    else:
                        current['text'] += ' ' + text
    if current:
        questions.append(current)
    return questions, highlight_map


def _apply(questions, mark_fn):
    """mark_fn(choice, qi) -> bool correct. Return new question dicts with
    is_correct set and choice text cleaned."""
    out = []
    for qi, q in enumerate(questions):
        choices = []
        for ch in q['choices']:
            choices.append({'text': clean_text(ch['raw']), 'is_correct': bool(mark_fn(ch, qi))})
        out.append({'text': clean_text(q['text']), 'choices': choices})
    return out


def validate(questions):
    if not questions:
        return ['no questions parsed']
    issues = []
    for i, q in enumerate(questions):
        nc = len(q['choices'])
        ncorr = sum(c['is_correct'] for c in q['choices'])
        if nc < 2:
            issues.append(f'q{i+1}: {nc} choices')
        if ncorr != 1:
            issues.append(f'q{i+1}: {ncorr} correct')
    return issues


def _detectors(questions, highlight_map):
    """Yield (name, marked_questions) for each answer-marking strategy."""
    # distinct choice text colors
    text_colors = set()
    hl_colors = set()
    for q in questions:
        for ch in q['choices']:
            if ch['color'] is not None:
                text_colors.add(ch['color'])
    for pi, cmap in highlight_map.items():
        hl_colors.update(cmap.keys())

    # highlight rect by color. When choices share a line (x0/x1 known), require
    # the highlight to sit over THIS choice horizontally, not just on the row —
    # otherwise every choice on a one-line "a. X  b. Y  c. Z" row matches.
    def _hl_over(ch, rect):
        cy = (ch['y0'] + ch['y1']) / 2
        if not (rect.y0 <= cy <= rect.y1):
            return False
        x0 = ch.get('x0')
        if x0 is None:
            return True  # no x info (separate-line choice): row match is enough
        return x0 <= (rect.x0 + rect.x1) / 2 <= ch['x1']

    for color in hl_colors:
        def mark(ch, qi, _c=color):
            return any(_hl_over(ch, r) for r in highlight_map.get(ch['page'], {}).get(_c, []))
        yield (f'highlight:{color:06x}', _apply(questions, mark))

    # colored choice text
    for color in text_colors:
        def mark(ch, qi, _c=color):
            return ch['color'] == _c
        yield (f'textcolor:{color:06x}', _apply(questions, mark))

    # any non-neutral colored text (handles a doc that mixes shades, e.g. ff0000
    # and ee0000, to mark answers)
    if len(text_colors) >= 1:
        yield ('anycolor', _apply(questions, lambda ch, qi: ch['color'] is not None))

    # any highlight color (mixed highlight shades)
    if len(hl_colors) >= 1:
        def mark_anyhl(ch, qi):
            for rects in highlight_map.get(ch['page'], {}).values():
                if any(_hl_over(ch, r) for r in rects):
                    return True
            return False
        yield ('anyhighlight', _apply(questions, mark_anyhl))

    # correct choice marked with a trailing asterisk ("Stop the burning process*")
    if any(ch.get('star') for q in questions for ch in q['choices']):
        yield ('star', _apply(questions, lambda ch, qi: ch.get('star', False)))

    # bold choice
    yield ('bold', _apply(questions, lambda ch, qi: ch['bold']))

    # trailing citation
    yield ('citation', _apply(questions, lambda ch, qi: ch['citation']))


# An answer-list entry: a number, then a run of period/paren separators OR just
# whitespace ("1. B", "1) B", "1.) B", "1    B."), then the value. The separator
# is a RUN so a "1.)" style key (period AND paren) doesn't leave a stray ")" glued
# to the answer letter.
_ANSWER_ENTRY_RE = re.compile(r'^\(?(\d{1,2})(?:[\.\)]+|\s+)\s*(.*)$')


_ANSWER_LETTER_RE = re.compile(r'^\(?[A-Ea-e](?:[\.\):\-\s]|$)')
_BARE_NUM_RE = re.compile(r'^\(?(\d{1,2})\)?$')


def _answers_from_text(text):
    """Parse a numbered answer list. Handles the answer on the same line
    ("1. B" / "1   B."), split across lines ("1." then "B"), entries whose
    number has no trailing period, and columnar keys where a bare number line is
    followed by the answer letter on the next line ("1" ⏎ "E" ⏎ source...)."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    answers = {}
    i = 0
    while i < len(lines):
        m = _ANSWER_ENTRY_RE.match(lines[i])
        if m:
            num, val = int(m.group(1)), m.group(2).strip()
            if not val and i + 1 < len(lines) and _ANSWER_LETTER_RE.match(lines[i + 1]):
                val = lines[i + 1].strip()
                i += 1
            if val:
                answers[num] = val
        elif _BARE_NUM_RE.match(lines[i]) and i + 1 < len(lines) and _ANSWER_LETTER_RE.match(lines[i + 1]):
            # bare number line, answer letter on the next line (page/source values
            # after it are numeric or long, so they don't form false answers)
            answers[int(_BARE_NUM_RE.match(lines[i]).group(1))] = lines[i + 1].strip()
            i += 1
        i += 1
    return answers


def parse_answer_list(pdf_path, start_page=0):
    reader = pypdf.PdfReader(pdf_path)
    text = '\n'.join(p.extract_text() for p in reader.pages[start_page:])
    return _answers_from_text(text)


def parse_qa_table(pdf_path):
    """Parse a columnar 'Q. | A. | Module | Page' answer sheet. Requires the
    Q/A column header, then reads each row "N  x  <module>  <page>" (or the same
    values one-per-line) as question number N -> answer letter x."""
    reader = pypdf.PdfReader(pdf_path)
    text = '\n'.join(p.extract_text() for p in reader.pages)
    if not re.search(r'\bQ\.?\s+A\.?\b', text, re.I):
        return {}
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    answers = {}
    # row form: "1  b  1  3"
    for l in lines:
        m = re.match(r'^(\d{1,2})\s+([a-eA-E])(?:\s|$)', l)
        if m:
            answers[int(m.group(1))] = m.group(2)
    # one-per-line fallback: N then a lone letter on the next line
    if not answers:
        for i, tok in enumerate(lines):
            if tok.isdigit() and i + 1 < len(lines) and re.fullmatch(r'[a-eA-E]', lines[i + 1]):
                answers[int(tok)] = lines[i + 1]
    return answers


_HASHKEY_RE = re.compile(r'^\s*A\s*#\s*(\d{1,2})\)\s*(.*)$', re.I)


def parse_hash_key(pdf_path):
    """Parse an "A#N)  X) source" embedded answer key (Southern/Southwest Regional
    template). Handles the letter on the same line ("A#10)  D) Module 4…") and the
    letter split onto the next line ("A#1)" then "A) Module 1…"), which is how the
    first column of these keys extracts."""
    doc = fitz.open(pdf_path)
    answers = {}
    for page in doc:
        lines = [l.strip() for l in page.get_text().split('\n') if l.strip()]
        for i, l in enumerate(lines):
            m = _HASHKEY_RE.match(l)
            if not m:
                continue
            num, rest = int(m.group(1)), m.group(2).strip()
            lm = re.match(r'^\(?([A-Ea-e])\b', rest)
            if lm:
                answers[num] = lm.group(1).upper()
            elif i + 1 < len(lines):
                lm2 = re.match(r'^\(?([A-Ea-e])\b', lines[i + 1])
                if lm2:
                    answers[num] = lm2.group(1).upper()
    return answers


def find_hash_key_page(pdf_path):
    """Index of the first page holding an A#N) answer key (>=5 entries), or None."""
    doc = fitz.open(pdf_path)
    for pi, page in enumerate(doc):
        hits = sum(1 for l in page.get_text().split('\n') if _HASHKEY_RE.match(l.strip()))
        if hits >= 5:
            return pi
    return None


def find_answer_key_page(pdf_path):
    """Index of the first page that is an embedded answer key — a page that
    parses as a numbered list whose values are predominantly single A-E letters
    (the answers listed at the end of the same test PDF, under any heading), or
    None."""
    doc = fitz.open(pdf_path)
    for pi, page in enumerate(doc):
        ans = _answers_from_text(page.get_text())
        if len(ans) >= 5:
            letters = sum(1 for v in ans.values()
                          if re.match(r'^[A-Ea-e](?:[\.\):\-\s]|$)', v.strip()))
            if letters >= 0.6 * len(ans):
                return pi
    return None


# a trailing statement-of-fact source ref on a key word ("triangle  SF # 99",
# "hurry SF#49", "physical # 47") — stripped so the bare answer word remains.
_SF_REF_RE = re.compile(r'\s*(?:SF\s*#?|#)\s*\d+\s*$', re.I)


def _word_key(text):
    """Parse a word-answer key ("1. medically", "5. 5", "3. user", "1. triangle
    SF # 99") -> {num: word}, dropping any trailing 'SF # N' source reference."""
    answers = {}
    for line in (l.strip() for l in text.split('\n') if l.strip()):
        m = re.match(r'^\(?(\d{1,2})[\.\)]\s+(.+)$', line)
        if m and not re.fullmatch(r'[A-Ea-e]', m.group(2).strip()):
            word = _SF_REF_RE.sub('', m.group(2).strip()).strip()
            if word:
                answers[int(m.group(1))] = word
    return answers


def sof_candidate(tpath):
    """Statement-of-fact tests: numbered statement + 2-3 unlabeled column choices,
    with the correct WORD given in an end-of-document key. Returns marked
    questions (matching key word to choice text) or None."""
    try:
        import sof_extract
        doc = fitz.open(tpath)
    except Exception:
        return None
    kp, keywords = None, None
    for pi, page in enumerate(doc):
        txt = page.get_text()
        if re.search(r'\banswers?\b', txt, re.I):
            wk = _word_key(txt)
            if len(wk) >= 5:
                kp, keywords = pi, wk
                break
    # Fallback: a page that IS a clean short-word numbered list is a key even when
    # it isn't labeled "answers" (e.g. "1. triangle  SF # 99" under a plain "…
    # Written Exam" heading). Question pages fail this — their values are long
    # statements, not 1-3 word answers.
    if kp is None:
        for pi, page in enumerate(doc):
            wk = _word_key(page.get_text())
            if len(wk) >= 5 and sum(1 for v in wk.values() if len(v.split()) <= 3) >= 0.8 * len(wk):
                kp, keywords = pi, wk
                break
    if kp is None:
        return None
    qs = sof_extract.parse_sof(tpath, max_pages=kp)
    real = [q for q in qs if len(q['choices']) >= 2]
    if not real:
        return None
    marked = []
    for q in real:
        ans = keywords.get(q['number'], '').strip().lower()
        choices = [clean_text(c) for c in q['choices']]
        idx = next((j for j, c in enumerate(choices) if c.strip().lower() == ans), -1)
        if idx < 0 and ans:
            idx = next((j for j, c in enumerate(choices)
                        if c.strip().lower() in ans or ans in c.strip().lower()), -1)
        marked.append({'text': clean_text(q['text']),
                       'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(choices)]})
    return marked


def _hl_answer_words(doc, page_indexes):
    """{qnum: 'highlighted words'} from a highlighted ANSWER section — an
    end-of-doc copy of the statement test where the correct fill-in word(s) are
    highlighted inside each numbered statement (Ohio Valley / NMRA Post 6 style)."""
    ans = {}
    for pi in page_indexes:
        page = doc[pi]
        rects = []
        for dr in page.get_drawings():
            f = dr.get('fill')
            if f and dr.get('type') in ('f', 'fs'):
                r, g, b = [int(x * 255) for x in f]
                if not _is_neutral((r << 16) | (g << 8) | b) and dr['rect'].width < page.rect.width * 0.7:
                    rects.append(dr['rect'])
        if not rects:
            continue
        cur = None
        for w in sorted(page.get_text('words'), key=lambda w: (round(w[1] / 3) * 3, w[0])):
            if re.match(r'^\(?(\d{1,2})[\.\)]$', w[4]) and w[0] < page.rect.width * 0.25:
                cur = int(re.match(r'\(?(\d{1,2})', w[4]).group(1)); ans.setdefault(cur, [])
                continue
            if cur is None:
                continue
            cy, cx = (w[1] + w[3]) / 2, (w[0] + w[2]) / 2
            if any(r.y0 <= cy <= r.y1 and r.x0 <= cx <= r.x1 for r in rects):
                ans[cur].append(w[4])
    return {k: ' '.join(v) for k, v in ans.items() if v}


def _norm_words(s):
    return set(re.sub(r'[^a-z0-9 ]', ' ', s.lower()).split())


def sof_highlight_candidate(tpath):
    """Statement-of-fact test whose answers are a highlighted copy of the test at
    the back (correct fill-in word highlighted in each statement). Parse the
    questions from the front, the highlighted words from the answer section, and
    mark the choice with the most word overlap with the highlighted answer."""
    try:
        import sof_extract
        doc = fitz.open(tpath)
    except Exception:
        return None
    def _page_has_hl(page):
        for dr in page.get_drawings():
            f = dr.get('fill')
            if f and dr.get('type') in ('f', 'fs') and dr['rect'].width < page.rect.width * 0.7:
                r, g, b = [int(x * 255) for x in f]
                if not _is_neutral((r << 16) | (g << 8) | b):
                    return True
        return False

    hl_pages = [pi for pi, page in enumerate(doc) if _page_has_hl(page)]
    if not hl_pages:
        return None
    first_ans = hl_pages[0]
    if first_ans == 0:
        return None  # answers must come after the question pages
    answers = _hl_answer_words(doc, hl_pages)
    if len(answers) < 5:
        return None
    qs = sof_extract.parse_sof(tpath, max_pages=first_ans)
    real = [q for q in qs if len(q['choices']) >= 2 and q['number'] in answers]
    if len(real) < 5:
        return None
    marked = []
    for q in real:
        aw = _norm_words(answers[q['number']])
        choices = [clean_text(c) for c in q['choices']]
        scores = [len(aw & _norm_words(c)) for c in choices]
        best = max(scores)
        idx = scores.index(best) if best > 0 and scores.count(best) == 1 else -1
        marked.append({'text': clean_text(q['text']),
                       'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(choices)]})
    return marked


def _answer_list_candidates(raw_questions, answers):
    """Yield (scheme, marked_questions) matching a numbered answer list (letter
    or text) to the questions, by question number and by position. Shared by the
    separate-answer-doc and embedded-answer-key paths."""
    if not raw_questions or not answers:
        return
    # A letter key often carries a page ref on the same line ("B  pg. 1-3");
    # if most values start with a bare A-E letter, reduce each to that letter.
    # A single-letter answer is the leading A-E followed by a separator: period,
    # paren, colon, dash, COMMA ("A, 3-16"), or whitespace ("B - False"), or EOL.
    # A following comma is a separator, not a second answer letter — but a bare
    # "A,B,&C" multi-answer has a LETTER after the comma, which this still excludes
    # via the reduction below (it keys on the strict single-letter head only).
    _single = r'^[A-Ea-e](?:[\.\):\-,\s]|$)'
    letterish = sum(1 for v in answers.values() if re.match(_single, v.strip())
                    and not re.match(r'^[A-Ea-e]\s*,\s*[A-Ea-e]', v.strip()))
    if letterish >= 0.7 * len(answers):
        # Reduce each SINGLE-letter answer to its bare letter. Multi-answer
        # entries ("A,B,&C" — every option correct) have a letter right after the
        # comma, so they're excluded here rather than silently collapsed to their
        # first letter and mis-marked as the sole answer.
        answers = {k: re.match(r'^[A-Ea-e]', v.strip()).group(0)
                   for k, v in answers.items()
                   if re.match(_single, v.strip())
                   and not re.match(r'^[A-Ea-e]\s*,\s*[A-Ea-e]', v.strip())}
    real = [q for q in raw_questions if len(q['choices']) >= 2]
    # Require that the parsed questions cover most of the answer key entries that
    # fall in their number range. A big shortfall means the test is sectioned
    # (numbering restarts per section, so matching a linear key by number would
    # mis-assign answers) or largely unparsed — don't emit a wrong quiz then.
    # Restricting to the question-number range lets a multiple-choice section
    # (nums 1..10) validate against a key that also covers a later parts section.
    qnums = [q['number'] for q in real if q.get('number')]
    if qnums:
        lo, hi = min(qnums), max(qnums)
        relevant = [k for k in answers if lo <= k <= hi]
        if relevant and len(real) < 0.8 * len(relevant):
            return
    elif len(real) < 0.8 * len(answers):
        return
    for scheme in ('number', 'position'):
        marked = []
        for i, q in enumerate(real):
            key = q.get('number') if scheme == 'number' else (i + 1)
            idx = _match_choice([{'text': clean_text(c['raw'])} for c in q['choices']],
                                answers.get(key, ''))
            marked.append({
                'text': clean_text(q['text']),
                'choices': [{'text': clean_text(c['raw']), 'is_correct': j == idx}
                            for j, c in enumerate(q['choices'])],
            })
        # The answer key is authoritative, so a question whose keyed answer didn't
        # map to a parsed choice is a per-question parse hiccup; drop those few
        # rather than failing the whole quiz — but only if the vast majority match,
        # so a real misalignment (wrong scheme) still fails.
        matched = [q for q in marked if sum(c['is_correct'] for c in q['choices']) == 1]
        if matched and len(matched) >= 0.9 * len(marked):
            yield scheme, matched
        else:
            yield scheme, marked


_TF_VALS = {'t', 'f', 'true', 'false'}
_TF_TAIL = re.compile(r'\s*\bT\s*(?:rue)?\s*(?:or|/|,|&)?\s*F\s*(?:alse)?\b\.?\s*$', re.I)
# a trailing leaked choice ("A. True", "B False", "Positive") and the fill-in
# answer blank ("_____"), stripped from a T/F statement stem.
_TF_LEAK = re.compile(
    r'[\s_]*(?:[ABab][\.\)]?\s+)?(?:True|False|Positive|Negative|Before|After)[\s_]*$', re.I)


def _clean_tf_stem(text):
    """Clean a True/False statement stem: drop a trailing 'T or F', a leaked
    'A. True'/'B. False' choice, and the trailing answer blank '_____'."""
    t = _TF_TAIL.sub('', text)
    prev = None
    while prev != t:
        prev = t
        t = _TF_LEAK.sub('', t).strip()
    t = re.sub(r'[\s_]+$', '', t).strip()
    return clean_text(t)


def tf_questions(raw_questions, answers):
    """Build True/False questions from statement-style questions ("<statement>\nT
    or F") plus a T/F answer key ({num: 'T'/'F'/'True'/'False'}). Returns marked
    [{text, choices:[True/False]}] or None when the key isn't predominantly T/F."""
    if not answers:
        return None
    vals = [str(v).strip().lower().rstrip('.') for v in answers.values()]
    if sum(1 for v in vals if v in _TF_VALS) < 0.8 * len(answers):
        return None
    out = []
    for q in raw_questions:
        n = q.get('number')
        if n not in answers:
            continue
        a = str(answers[n]).strip().lower().rstrip('.')
        if a not in _TF_VALS:
            continue
        correct_true = a in ('t', 'true')
        stem = _clean_tf_stem(q['text'])
        if not stem:
            continue
        out.append({'text': stem, 'choices': [
            {'text': 'True', 'is_correct': correct_true},
            {'text': 'False', 'is_correct': not correct_true}]})
    return out or None


def tf_mixed_questions(raw_questions, answers):
    """A test whose key is A/B(/C/D) letters and whose questions are mostly True/
    False statements ("<statement>?  A. True  B. False") but where the T/F options
    inconsistently parse — some questions show only "_____". For each question use
    its real parsed choices when they're a genuine multiple-choice set; otherwise
    synthesize [True, False] and map the keyed letter A->True, B->False. Only fires
    when the test is T/F-dominant, so normal MC tests are unaffected."""
    if not answers:
        return None
    letters = {k: str(v).strip().upper() for k, v in answers.items()
               if re.match(r'^[A-Ea-e]$', str(v).strip())}
    if len(letters) < 0.8 * len(answers):
        return None
    covered = [q for q in raw_questions if q.get('number') in letters]
    if not covered:
        return None

    def parsed_choices(q):
        return [clean_text(c['raw']) for c in q['choices'] if clean_text(c['raw']).strip()]

    def is_tf(q):
        pc = [c.strip().lower() for c in parsed_choices(q)]
        return len(pc) < 2 or all(c in ('true', 'false') for c in pc)

    if sum(1 for q in covered if is_tf(q)) < 0.6 * len(covered):
        return None  # not a True/False-dominant test
    out = []
    for q in covered:
        idx = 'ABCDE'.index(letters[q['number']])
        pc = parsed_choices(q)
        if len(pc) >= 2 and not all(c.strip().lower() in ('true', 'false') for c in pc):
            choices = [{'text': c, 'is_correct': j == idx} for j, c in enumerate(pc)]
        elif idx in (0, 1):
            choices = [{'text': 'True', 'is_correct': idx == 0},
                       {'text': 'False', 'is_correct': idx == 1}]
        else:
            continue
        stem = _clean_tf_stem(q['text'])
        if stem and sum(c['is_correct'] for c in choices) == 1:
            out.append({'text': stem, 'choices': choices})
    return out or None


def _match_choice(choices, ans):
    a = ans.strip().lower().rstrip('.')
    if not a:
        return None
    if len(a) == 1 and a in 'abcde':
        i = 'abcde'.index(a)
        return i if i < len(choices) else None
    # letter prefix like "b. 78 to 21"
    m = re.match(r'^([a-e])[\.\)]\s*(.*)$', a)
    if m:
        i = 'abcde'.index(m.group(1))
        if i < len(choices):
            return i
    for i, c in enumerate(choices):
        cc = c['text'].strip().lower().rstrip('.')
        if cc and (cc == a or cc in a or a in cc):
            return i
    return None


def extract(test_file, answer_file, max_pages=None):
    from django.conf import settings  # lazy: keeps this module importable without Django
    tpath = os.path.join(settings.MEDIA_ROOT, test_file) if test_file else None
    apath = os.path.join(settings.MEDIA_ROOT, answer_file) if answer_file else None

    # Deterministic priority so a stronger, less-spurious signal always wins
    # over a weaker one instead of picking by question count.
    DETECTOR_RANK = {'highlight': 0, 'textcolor': 1, 'star': 1, 'anyhighlight': 2, 'anycolor': 2,
                     'citation': 3, 'bold': 5}
    SOURCE_RANK = {'key': 0, 'self': 1}

    candidates = []  # (rank, clean_bool, n_issues, method, questions)

    def consider(source_path, label):
        if not source_path:
            return
        try:
            questions, hmap = extract_questions(source_path, max_pages=max_pages)
        except Exception:
            return
        if not questions:
            return
        # Drop stray choice-less items (a numbered directions preamble, a section
        # header, or a lone question whose choices failed to parse) so one of them
        # doesn't fail the whole quiz — but only when they're a clear minority, so
        # a genuinely unparseable doc still fails instead of yielding a stub quiz.
        empty = [q for q in questions if len(q['choices']) < 2]
        if empty and len(empty) < len(questions) * 0.5:
            questions = [q for q in questions if len(q['choices']) >= 2]
        for name, marked in _detectors(questions, hmap):
            det = name.split(':')[0]
            rank = SOURCE_RANK[label] * 10 + DETECTOR_RANK.get(det, 5)
            iss = validate(marked)
            candidates.append((rank, len(iss) == 0, len(iss), f'{label}/{name}', marked))
            # If a detector marks all-but-a-few questions with exactly one correct,
            # the stragglers are usually a question whose answer mark didn't parse;
            # offer a variant that drops just those (never adds a wrong answer).
            good = [q for q in marked if sum(c['is_correct'] for c in q['choices']) == 1]
            if iss and len(good) >= 8 and len(good) >= 0.9 * len(marked) and len(good) < len(marked):
                candidates.append((rank + 1, True, 0, f'{label}/{name}(most)', good))

    consider(apath, 'key')
    consider(tpath, 'self')

    # separate numbered answer-list doc (rank between citation and bold)
    if tpath and apath:
        try:
            raw = extract_questions(tpath, max_pages=max_pages)[0]
            for answers in (parse_answer_list(apath), parse_qa_table(apath)):
                for scheme, marked in _answer_list_candidates(raw, answers):
                    iss = validate(marked)
                    candidates.append((3, len(iss) == 0, len(iss), f'separate-list/{scheme}', marked))
        except Exception:
            pass

    # True/False statement tests: "<statement>  T or F" + a T/F (or A/B) answer
    # key, from a separate answer doc or embedded at the end of the test itself.
    # Each key is paired with questions read from the RIGHT page range so the key
    # page's own "1. B" lines aren't picked up as extra questions.
    if tpath:
        try:
            ekp = find_answer_key_page(tpath)
            tf_keys = []  # (answers, questions)
            if apath:
                tf_keys.append((parse_answer_list(apath),
                                extract_questions(tpath, max_pages=max_pages)[0]))
            if ekp:
                qmax = min(ekp, max_pages) if max_pages else ekp
                tf_keys.append((parse_answer_list(tpath, start_page=ekp),
                                extract_questions(tpath, max_pages=qmax)[0]))
            for answers, raw in tf_keys:
                marked = tf_questions(raw, answers)
                if marked:
                    iss = validate(marked)
                    candidates.append((3, len(iss) == 0, len(iss), 'true-false', marked))
                mixed = tf_mixed_questions(raw, answers)
                if mixed:
                    iss = validate(mixed)
                    candidates.append((3, len(iss) == 0, len(iss), 'true-false-mixed', mixed))
                    good = [q for q in mixed if sum(c['is_correct'] for c in q['choices']) == 1]
                    if iss and len(good) >= 8 and len(good) >= 0.85 * len(mixed):
                        candidates.append((3, True, 0, 'true-false-mixed(most)', good))
        except Exception:
            pass

    # statement-of-fact tests: unlabeled column choices + end-of-doc word key
    if tpath and not any(c[1] for c in candidates):
        try:
            marked = sof_candidate(tpath)
            if marked:
                iss = validate(marked)
                candidates.append((4, len(iss) == 0, len(iss), 'statement-of-fact', marked))
                good = [q for q in marked if sum(c['is_correct'] for c in q['choices']) == 1]
                if iss and len(good) >= 8 and len(good) >= 0.9 * len(marked):
                    candidates.append((4, True, 0, 'statement-of-fact(most)', good))
        except Exception:
            pass

    # statement-of-fact whose answers are a highlighted copy of the test at the back
    if tpath and not any(c[1] for c in candidates):
        try:
            marked = sof_highlight_candidate(tpath)
            if marked:
                iss = validate(marked)
                candidates.append((4, len(iss) == 0, len(iss), 'sof-highlight', marked))
                good = [q for q in marked if sum(c['is_correct'] for c in q['choices']) == 1]
                if iss and len(good) >= 8 and len(good) >= 0.85 * len(marked):
                    candidates.append((4, True, 0, 'sof-highlight(most)', good))
        except Exception:
            pass

    # "A#N)" embedded key on a Q#/A# template doc (Southern/Southwest Regional)
    if tpath:
        try:
            hk_page = find_hash_key_page(tpath)
            if hk_page is not None:
                answers = parse_hash_key(tpath)
                qmax = min(hk_page, max_pages) if max_pages else hk_page
                raw = extract_questions(tpath, max_pages=qmax)[0]
                for scheme, marked in _answer_list_candidates(raw, answers):
                    iss = validate(marked)
                    candidates.append((3, len(iss) == 0, len(iss), f'embedded-key/hash-{scheme}', marked))
        except Exception:
            pass

    # answer key embedded at the end of the test doc itself ("ANSWER KEY" section)
    if tpath:
        try:
            key_page = find_answer_key_page(tpath)
            if key_page:
                # stop before a parts section too (max_pages), not just the key
                qmax = min(key_page, max_pages) if max_pages else key_page
                raw = extract_questions(tpath, max_pages=qmax)[0]
                answers = parse_answer_list(tpath, start_page=key_page)
                for scheme, marked in _answer_list_candidates(raw, answers):
                    iss = validate(marked)
                    candidates.append((3, len(iss) == 0, len(iss), f'embedded-key/{scheme}', marked))
        except Exception:
            pass

    if not candidates:
        return {'method': None, 'questions': None, 'issues': ['no strategy produced questions'], 'clean': False}

    clean = [c for c in candidates if c[1]]
    if clean:
        best = min(clean, key=lambda c: c[0])  # lowest rank = most reliable signal
        return {'method': best[3], 'questions': best[4], 'issues': [], 'clean': True}

    # Leading-run recovery: some docs are a clean multiple-choice section followed
    # by an un-quizzable one (e.g. image-based parts-identification questions whose
    # choices reference a diagram). If a candidate's questions validate as a clean
    # PREFIX and everything after the prefix is invalid, keep just the prefix.
    def leading_run(qs):
        k = 0
        for q in qs:
            if len(q['choices']) >= 2 and sum(c['is_correct'] for c in q['choices']) == 1:
                k += 1
            else:
                break
        return k

    trunc = []
    for rank, _c, _n, method, qs in candidates:
        if not qs:
            continue
        k = leading_run(qs)
        # require a substantial clean prefix and that the REST is genuinely bad
        # (nothing valid after the run, so we're not dropping a stray good question)
        if k >= 5 and k < len(qs) and not any(
            len(q['choices']) >= 2 and sum(c['is_correct'] for c in q['choices']) == 1
            for q in qs[k:]
        ):
            trunc.append((rank, k, method, qs[:k]))
    if trunc:
        trunc.sort(key=lambda t: (t[0], -t[1]))
        rank, k, method, qs = trunc[0]
        return {'method': f'{method}(prefix {k})', 'questions': qs, 'issues': [], 'clean': True, 'truncated': True}

    best = min(candidates, key=lambda c: (c[2], c[0]))
    return {'method': best[3] + '(partial)', 'questions': best[4], 'issues': validate(best[4]) if best[4] else ['n/a'], 'clean': False}
