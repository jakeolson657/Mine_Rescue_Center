"""Build the Identification of Parts practice data from the bench contest rules.

Each bench rules PDF (Sections IV-VI in media/training/rules/) ends with an
"Identification of Parts" section: one page per assembly with a title, an
exploded diagram, and a "Cons. No. / Designation" table naming every numbered
callout. This script crops each diagram to pages/static/pages/parts/ and writes
pages/parts_data.json, which the parts practice pages read at request time.

Re-run whenever a new year's rules are uploaded:

    PYTHONUTF8=1 venv/Scripts/python.exe quiz_pipeline/build_parts_id.py

then eyeball the printed tables against the PDFs and commit the JSON + images.
"""
import json
import os
import re
import sys

import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parts_extract import _content_bbox  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_DIR = os.path.join(ROOT, 'media', 'training', 'rules')
STATIC_REL = 'pages/parts'
IMG_DIR = os.path.join(ROOT, 'pages', 'static', *STATIC_REL.split('/'))
OUT_JSON = os.path.join(ROOT, 'pages', 'parts_data.json')

# (slug, display name, rules PDF, words that identify the unit's
#  BenchingApparatus row by name). Listed in rules-section order.
UNITS = [
    ('biopak-240r', 'BioPak 240R', 'section-4-bio-240r-bench-rules.pdf', ['biopak']),
    ('bg4', 'BG4', 'section-5-bg-4-bench-rules.pdf', ['bg4', 'bg 4']),
    ('bg-proair', 'BG ProAir', 'section-6-bg-proair-oxygen-dosage-bench-rules.pdf', ['proair']),
]

# Callout labels: "7", "15A", "11-13", "1.2", "1-1.3", and "14-16," (lists).
NUM_RE = re.compile(r'^\d{1,3}(?:\.\d)?[A-Za-z]?(?:[-–]\d{1,3}(?:\.\d)?[A-Za-z]?)?,?$')

# Fixes the text layer can't express, keyed (unit slug, PDF page). Titles that
# are part of the scanned image, and red-pen corrections whose struck-through
# word is still in the text (the strikethrough isn't encoded per word).
TITLE_OVERRIDES = {
    ('bg-proair', 40): 'Test Kit',
}
NAME_OVERRIDES = {
    ('bg4', 27, '11'): 'Reaction Ring',  # "Compression" struck out in red
}
ROW_TOL = 4  # points; words whose tops are this close share a table row


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def clean_title(text):
    text = re.sub(r'\s*\(revised drawing\)\s*', ' ', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()


def find_title(words, header_top):
    """The assembly title: the largest-font line above the table. Using the
    tallest words skips stray callout numbers scattered over the diagram."""
    above = [w for w in words if w[3] < header_top and w[4].strip()]
    if not above:
        return None, None
    tallest = max(w[3] - w[1] for w in above)
    title_words = [w for w in above if (w[3] - w[1]) >= tallest - 1.5]
    first_top = min(w[1] for w in title_words)
    line = sorted((w for w in title_words if abs(w[1] - first_top) < ROW_TOL),
                  key=lambda w: w[0])
    return ' '.join(w[4] for w in line), max(w[3] for w in line)


def parse_table(words):
    """Return (parts, header_top) from a page's 'Cons. No. / Designation'
    table(s). parts is [(number_label, name)], or None if no table."""
    cons = sorted((w for w in words if w[4] == 'Cons.'), key=lambda w: w[0])
    desig = sorted((w for w in words if w[4].startswith('Designation')), key=lambda w: w[0])
    if not cons or len(cons) != len(desig):
        return None, None
    header_bottom = max(w[3] for w in cons + desig)
    # The "1  2" column-index row sits just above "Cons. No. Designation".
    header_top = min(w[1] for w in cons) - 18

    # One column per Cons. header: numbers start a little left of "Cons."
    # (they're right-aligned under it); names run from "Designation" to the
    # next column.
    cols = []
    for i, (c, d) in enumerate(zip(cons, desig)):
        right = cons[i + 1][0] - 4 if i + 1 < len(cons) else 10_000
        cols.append({'num_x0': c[0] - 20, 'name_x0': d[0] - 3, 'x1': right})

    # By vertical center: some first rows overlap the header's bottom edge.
    body = [w for w in words if (w[1] + w[3]) / 2 > header_bottom and w[4].strip()]
    body.sort(key=lambda w: (w[1], w[0]))
    rows = []
    for w in body:
        if rows and abs(w[1] - rows[-1][0]) < ROW_TOL:
            rows[-1][1].append(w)
        else:
            rows.append([w[1], [w]])

    parts = {i: [] for i in range(len(cols))}
    prev_top = {i: None for i in range(len(cols))}
    for top, row_words in rows:
        for ci, col in enumerate(cols):
            cw = sorted((w for w in row_words if col['num_x0'] <= w[0] < col['x1']),
                        key=lambda w: w[0])
            if not cw:
                continue
            # Leading callout labels, then the designation. Split on tokens,
            # not on the header's x: some names start left of "Designation".
            k = 0
            while k < len(cw) and cw[k][0] < col['name_x0'] - 8 and NUM_RE.match(cw[k][4]):
                k += 1
            label = ' '.join(w[4] for w in cw[:k]).replace('–', '-')
            name = ' '.join(w[4] for w in cw[k:])
            if label:
                parts[ci].append([label, name])
                prev_top[ci] = top
            elif name and parts[ci] and top - prev_top[ci] < 22:
                # Wrapped designation, e.g. "Test Connection for Control / Valve".
                parts[ci][-1][1] += ' ' + name
                prev_top[ci] = top
    out = []
    for ci in range(len(cols)):
        out.extend((n, re.sub(r'\s+', ' ', name).strip()) for n, name in parts[ci])
    return [p for p in out if p[1]], header_top


def iop_page_range(doc):
    """0-based page indexes of the Identification of Parts section, from the
    index page's 'Identification of Parts ... N' / 'Judge's Checklist ... M'."""
    index_text = doc[1].get_text()
    m1 = re.search(r'Identification of Parts\D*(\d+)', index_text)
    m2 = re.search(r'Judge.s Checklist\D*(\d+)', index_text)
    start, end = int(m1.group(1)), int(m2.group(1))
    # Printed page numbers don't match PDF indexes, so the section starts at
    # the first page with a diagram and a parts table.
    for pi in range(len(doc)):
        if doc[pi].get_images() and parse_table(doc[pi].get_text('words'))[0]:
            return list(range(pi, min(pi + (end - start), len(doc))))
    return []


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    for old in os.listdir(IMG_DIR):  # drop diagrams of renamed/removed assemblies
        if old.endswith('.png'):
            os.remove(os.path.join(IMG_DIR, old))
    data = []
    for slug, name, pdf, match in UNITS:
        doc = fitz.open(os.path.join(RULES_DIR, pdf))
        unit = {'slug': slug, 'name': name, 'match': match, 'rules_file': pdf, 'assemblies': []}
        for pi in iop_page_range(doc):
            if not doc[pi].get_images():
                continue  # past the last diagram (e.g. the Judge's Checklist)
            page = doc[pi]
            words = page.get_text('words')
            parts, header_top = parse_table(words)
            if not parts:
                print(f'!! {name} p{pi + 1}: no table parsed', file=sys.stderr)
                continue
            title, title_bottom = find_title(words, header_top)
            title = clean_title(TITLE_OVERRIDES.get((slug, pi + 1)) or title or f'Page {pi + 1}')
            parts = [(n, NAME_OVERRIDES.get((slug, pi + 1, n), nm)) for n, nm in parts]

            band = fitz.Rect(page.rect.x0 + 20, (title_bottom or 60) + 4,
                             page.rect.x1 - 20, header_top - 4)
            box = _content_bbox(page, band) or band
            box = fitz.Rect(box.x0 - 6, box.y0 - 6, box.x1 + 6, box.y1 + 6) & page.rect
            a_slug = slugify(title)
            img_name = f'{slug}-{a_slug}.png'
            pix = page.get_pixmap(clip=box, dpi=170, colorspace=fitz.csGRAY)
            pix.save(os.path.join(IMG_DIR, img_name))

            unit['assemblies'].append({
                'slug': a_slug,
                'title': title,
                'page': pi + 1,
                'image': f'{STATIC_REL}/{img_name}',
                'parts': [{'number': n, 'name': nm} for n, nm in parts],
            })
            print(f'== {name} p{pi + 1}: {title} ({len(parts)} parts)')
            for n, nm in parts:
                print(f'   {n:>6}  {nm}')
        data.append(unit)

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f'\nWrote {OUT_JSON}')


if __name__ == '__main__':
    main()
