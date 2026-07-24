"""Extract diagram-based 'parts identification' questions from Draeger 240R
bench-test PDFs. Each such page has: a title, an exploded diagram, a table
mapping consecutive part numbers to designations with a blank and a "(NN)"
question marker, and a choice grid where each column is one question (NN) with
A/B/C choices, the correct one colored red.

Produces questions of the form {'text', 'image_clip': Rect, 'choices':[...]}.
"""
import re
import fitz

QMARK_RE = re.compile(r'\((\d{1,2})\)')
CHOICE_LETTER_RE = re.compile(r'^([A-C])\.$')


def _red(color):
    if color is None:
        return False
    r = (color >> 16) & 255
    g = (color >> 8) & 255
    b = color & 255
    return r > 150 and g < 120 and b < 120


def _content_bbox(page, band, dpi=110, thresh=240):
    """Tight bounding box (PDF coords) of the non-white content inside `band`,
    found by rasterising the region and scanning for dark pixels. Returns None
    if the band is blank. Used to crop a diagram to just its ink."""
    pix = page.get_pixmap(clip=band, colorspace=fitz.csGRAY, dpi=dpi)
    w, h, s = pix.width, pix.height, pix.samples
    if not w or not h:
        return None
    table = bytes(1 if i < thresh else 0 for i in range(256))
    dark = b'\x01'
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        row = s[y * w:(y + 1) * w]
        if min(row) >= thresh:      # fully white row — skip fast
            continue
        mask = row.translate(table)
        left = mask.find(dark)
        right = mask.rfind(dark)
        if left < minx:
            minx = left
        if right > maxx:
            maxx = right
        if y < miny:
            miny = y
        maxy = y
    if maxx < 0:
        return None
    scale = dpi / 72.0
    return fitz.Rect(band.x0 + minx / scale, band.y0 + miny / scale,
                     band.x0 + (maxx + 1) / scale, band.y0 + (maxy + 1) / scale)


def first_parts_page(doc):
    """Index of the first page that parses as a parts section, or None."""
    for pi in range(len(doc)):
        qs, _ = extract_parts_page(doc[pi])
        if qs:
            return pi
    return None


def _color_at(spans, x, y):
    """Color of the span covering point (x,y), or 0."""
    for s in spans:
        if s['x0'] - 1 <= x <= s['x1'] + 1 and s['y0'] - 1 <= y <= s['y1'] + 1:
            return s['color']
    return 0


def extract_parts_page(page, answer_key=None):
    """Return (questions, diagram_clip) for one parts page, or ([], None).
    Correct choices are marked from a red highlight in the grid, or — when
    `answer_key` (a {question_number: 'A'/'B'/'C'} dict) is given — by the key
    letter. Questions with >=2 choices are returned even if no correct is marked;
    the caller filters to exactly-one-correct."""
    words = page.get_text('words')  # (x0,y0,x1,y1,word,block,line,wordno)
    d = page.get_text('dict')
    spans = []
    for block in d['blocks']:
        for line in block.get('lines', []):
            for s in line['spans']:
                if s['text'].strip():
                    spans.append({'text': s['text'], 'x0': s['bbox'][0], 'y0': s['bbox'][1],
                                  'x1': s['bbox'][2], 'y1': s['bbox'][3], 'color': s['color']})

    # 1. Choice letters A./B./C. as standalone words locate the grid.
    letters = [w for w in words if CHOICE_LETTER_RE.match(w[4])]
    if len(letters) < 6:
        return [], None
    grid_top = min(w[1] for w in letters)

    # 2. Column headers "(NN)" just above the grid.
    # Header markers sit in a single tight row just above the choice letters;
    # table markers are higher up. Separate by a small band above the grid.
    HEADER_BAND = 24
    headers = []
    for w in words:
        m = QMARK_RE.fullmatch(w[4])
        if m and grid_top - HEADER_BAND <= w[1] < grid_top - 1:
            headers.append({'num': int(m.group(1)), 'xc': (w[0] + w[2]) / 2})
    headers.sort(key=lambda h: h['xc'])
    if not headers:
        return [], None
    col_edges = []
    for i, h in enumerate(headers):
        left = (headers[i - 1]['xc'] + h['xc']) / 2 if i else -1e9
        right = (headers[i + 1]['xc'] + h['xc']) / 2 if i + 1 < len(headers) else 1e9
        col_edges.append((left, right))

    # 3. Build choices per column from the A/B/C letter words + trailing words.
    letter_words = sorted(letters, key=lambda w: (round(w[1]), w[0]))
    questions = []
    for i, h in enumerate(headers):
        lo, hi = col_edges[i]
        col_letters = [w for w in letter_words if lo <= w[0] < hi]
        choices = []
        for lw in col_letters:
            y = lw[1]
            # words on same row, to the right of this letter, within the column
            texts = [w for w in words if abs(w[1] - y) < 5 and w[0] > lw[0] and w[0] < hi
                     and not CHOICE_LETTER_RE.match(w[4]) and not QMARK_RE.fullmatch(w[4])]
            texts.sort(key=lambda w: w[0])
            text = ' '.join(w[4] for w in texts).strip()
            red = any(_red(_color_at(spans, (w[0] + w[2]) / 2, (w[1] + w[3]) / 2)) for w in texts)
            if text:
                choices.append({'letter': lw[4][0], 'text': text, 'is_correct': red})
        if answer_key is not None:
            key_letter = str(answer_key.get(h['num'], '')).strip().upper()[:1]
            for c in choices:
                c['is_correct'] = (c['letter'].upper() == key_letter)
        if len(choices) >= 2:
            questions.append({'num': h['num'], 'choices': choices})

    # 4. Stems from the table row that carries each "(NN)". The table can have two
    #    side-by-side column-pairs, so keep only words in the marker's own cell
    #    (a bounded window to its left) and drop the leading consecutive-part no.
    stems = {}
    STEM_WINDOW = 210
    for w in words:
        m = QMARK_RE.fullmatch(w[4])
        if not m or w[1] >= grid_top - HEADER_BAND:
            continue
        num = int(m.group(1))
        mx, my = w[0], (w[1] + w[3]) / 2
        row = [t for t in words
               if abs((t[1] + t[3]) / 2 - my) < 6
               and t[2] <= mx + 1 and t[0] >= mx - STEM_WINDOW
               and t[4].strip() and not QMARK_RE.fullmatch(t[4])]
        row.sort(key=lambda t: t[0])
        toks = [t[4] for t in row]
        part_no = None
        while toks and toks[0].strip().isdigit():   # leading cell = diagram callout no.
            part_no = toks.pop(0).strip()
            break
        txt = re.sub(r'_{2,}', ' ______ ', ' '.join(toks))
        txt = re.sub(r'\s+', ' ', txt).strip()
        stems[num] = (f'Part {part_no}: {txt}' if part_no and txt else txt)

    for q in questions:
        q['stem'] = stems.get(q['num'], '')

    # 5. Diagram clip: a band between the title and the parts TABLE, then cropped
    #    to the diagram's actual ink. The band bottom must sit ABOVE the table's
    #    topmost row (a "1  2" column-number row just above the "Cons. No."
    #    header) so no table text enters the image; the diagram's real bottom is
    #    well above this, so this only trims whitespace/table, never the drawing.
    title_bottom = max((w[3] for w in words if w[1] < 130), default=100)
    cons_top = min((w[1] for w in words if w[4].strip().rstrip('.').lower() in ('cons', 'designation')),
                   default=None)
    marker_top = min((w[1] for w in words if QMARK_RE.fullmatch(w[4]) and w[1] < grid_top - HEADER_BAND),
                     default=grid_top - HEADER_BAND)
    if cons_top:
        band_bot = cons_top - 18          # clears the "1 2" row above "Cons."
    else:
        band_bot = marker_top - 20
    band_top = title_bottom + 4

    # Drop any section-title text (e.g. "Manifold Assembly") sitting above the
    # illustration so only the part drawing is in the image. Title words are
    # alphabetic (the drawing's own labels are numeric callouts) and live in the
    # upper part of the band.
    header_zone = band_top + (band_bot - band_top) * 0.4
    header_words = [w for w in words
                    if band_top <= w[1] < header_zone and re.search(r'[A-Za-z]{3,}', w[4])]
    if header_words:
        band_top = max(w[3] for w in header_words) + 6

    # Crop tightly to the diagram's actual ink (the exploded illustration plus
    # its number callouts and leader lines), so the image is centered with only
    # a small uniform margin and no surrounding whitespace or table text.
    band = fitz.Rect(0, band_top, page.rect.width, band_bot)
    bbox = _content_bbox(page, band)
    if bbox:
        pad = 8
        clip = fitz.Rect(max(0, bbox.x0 - pad), max(0, bbox.y0 - pad),
                         min(page.rect.width, bbox.x1 + pad),
                         min(page.rect.height, bbox.y1 + pad))
    else:
        clip = band
    return questions, clip
