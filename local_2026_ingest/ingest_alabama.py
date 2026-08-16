"""Ingest the 2026 Alabama State Mine Rescue Contest folder.

Same family as ``ingest_kmi.py`` / ``ingest_co_in.py`` but this folder needs
three fix-ups the plain copy pattern can't do, so file generation happens here
instead of relying on ``miningquiz_ingest/convert_docs.py``:

1. The two "First Aid & Benchman" field PDFs are scanned SIDEWAYS (page box is
   portrait, content rotated). Each page's ``/Rotate`` is set so the content is
   upright -- a lossless display flag (no re-rasterizing), honored by the
   in-browser PDF viewer. Verified per-page orientation map (both files share
   the same layout): pages 2 & 3 (0-based idx 1,2 -- Problem Statement + Written
   Instructions) need 180; every other page needs 270.
2. The mine-rescue written test is ONE combined ``.docx`` holding both Day 1 and
   Day 2 exams. It is converted to PDF (Word COM) then SPLIT at the Day 2 exam
   title page into two separate documents.
3. The first-aid written test ``.docx`` is converted to a single PDF.

Alabama is Coal, but the folder holds no underground mine-rescue field problem --
only the combined First Aid & Benchman field packets and the written tests -- so
problems are named descriptively rather than ``Coal Day N Field``. Written tests
are consolidated into one ``Written Tests`` problem per site convention.

Links to the existing 2026 calendar event
"2026 Alabama Mine Rescue, First Aid & Benchman Competition" (Sumiton, AL).

Idempotent: a (problem, file) row is skipped when present and a media file is
only (re)generated when missing -- safe to re-run.

Run:  python local_2026_ingest/ingest_alabama.py        (use --dry-run to preview)
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from pages.models import (  # noqa: E402
    CalendarEvent, Competition, CompetitionProblem, ProblemDocument,
)
from pypdf import PdfReader, PdfWriter  # noqa: E402

MEDIA = settings.MEDIA_ROOT
ONEDRIVE = r"C:\Users\Jacob\OneDrive - Colorado School of Mines\Documents\Mine Rescue Center\Past Problems\2026"
YEAR = 2026
FOLDER = "Alabama Mine Rescue Competition"
ANCHOR = "Alabama"
EVENT_TITLE = "2026 Alabama Mine Rescue, First Aid & Benchman Competition"
COMP_NAME = "Alabama State Mine Rescue Contest"

# Source filenames in the competition folder.
FIELD_DAY1 = "First Aid & Benchman Competition Day 1.pdf"
FIELD_DAY2 = "First Aid & Benchman Competition Day 2.pdf"
WRITTEN_COMBINED = "Alabama 2026 Mine Rescue Contest Written Tests.docx"
FIRST_AID_WRITTEN = "2026 Alabama First Aid Contest written test.docx"

# Per-page /Rotate for the sideways field scans (0-based page index).
FIELD_ROT_OVERRIDES = {1: 180, 2: 180}
FIELD_ROT_DEFAULT = 270


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def norm(txt):
    return re.sub(r"[^a-z0-9]+", "", (txt or "").lower())


def derotate(src, dst):
    """Copy PDF setting each page's /Rotate so content reads upright (lossless)."""
    reader = PdfReader(src)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        # Pages start at /Rotate 0, so .rotate() sets the absolute angle.
        page.rotate(FIELD_ROT_OVERRIDES.get(i, FIELD_ROT_DEFAULT))
        writer.add_page(page)
    with open(dst, "wb") as fh:
        writer.write(fh)
    return len(reader.pages)


def word_to_pdf(app, src, dst):
    doc = app.Documents.Open(os.path.abspath(src), ReadOnly=True, AddToRecentFiles=False)
    doc.SaveAs(os.path.abspath(dst), FileFormat=17)  # wdFormatPDF
    doc.Close(False)


def split_written(pdf_path, day1_dst, day2_dst):
    """Split the combined written-test PDF at the Day 2 exam title page."""
    reader = PdfReader(pdf_path)
    title_pages = [i for i, p in enumerate(reader.pages)
                   if "writtenexam" in norm(p.extract_text())]
    day2_pages = [i for i, p in enumerate(reader.pages)
                  if "writtenexamday2" in norm(p.extract_text())]
    if not day2_pages:
        raise RuntimeError(
            f"Could not find the 'Written Exam - Day 2' title page in {pdf_path}. "
            f"Pages with 'Written Exam': {title_pages}")
    day2_start = day2_pages[0]
    print(f"      split: {len(reader.pages)} pages; 'Written Exam' title pages "
          f"{title_pages}; Day 2 starts at page {day2_start + 1}")
    for dst, rng in ((day1_dst, range(0, day2_start)),
                     (day2_dst, range(day2_start, len(reader.pages)))):
        w = PdfWriter()
        for i in rng:
            w.add_page(reader.pages[i])
        with open(dst, "wb") as fh:
            w.write(fh)


def is_pdf(path):
    return os.path.exists(path) and open(path, "rb").read(5) == b"%PDF-"


def build_media(src_dir, do_write):
    """Produce the five target PDFs under media/problems; return {key: rel_path}."""
    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)

    def rel(problem_title, out_name):
        return "problems/" + safe_filename(slugify(problem_title), out_name)

    targets = {
        "field1": rel("First Aid & Benchman Day 1", "Field.pdf"),
        "field2": rel("First Aid & Benchman Day 2", "Field.pdf"),
        "w1": rel("Written Tests", "Mine Rescue Written Test - Day 1.pdf"),
        "w2": rel("Written Tests", "Mine Rescue Written Test - Day 2.pdf"),
        "fa": rel("Written Tests", "First Aid Written Test.pdf"),
    }
    for key, r in targets.items():
        print(f"  target[{key}] -> {r}")

    if not do_write:
        for f in (FIELD_DAY1, FIELD_DAY2, WRITTEN_COMBINED, FIRST_AID_WRITTEN):
            p = os.path.join(src_dir, f)
            print(f"  {'ok ' if os.path.exists(p) else 'MISSING'} source: {f}")
        return targets

    abspath = {k: os.path.join(MEDIA, v) for k, v in targets.items()}

    # 1. Field PDFs -- de-rotate.
    for key, src_name in (("field1", FIELD_DAY1), ("field2", FIELD_DAY2)):
        if is_pdf(abspath[key]):
            print(f"  = {key} already present")
            continue
        n = derotate(os.path.join(src_dir, src_name), abspath[key])
        print(f"  + de-rotated {src_name} ({n} pages) -> {targets[key]}")

    # 2 & 3. Word conversions (open Word once), split combined written test.
    need_word = not (is_pdf(abspath["w1"]) and is_pdf(abspath["w2"])
                     and is_pdf(abspath["fa"]))
    if need_word:
        import win32com.client as win32
        app = win32.Dispatch("Word.Application")
        app.Visible = False
        try:
            app.DisplayAlerts = 0
        except Exception:  # noqa: BLE001
            pass
        try:
            if not (is_pdf(abspath["w1"]) and is_pdf(abspath["w2"])):
                tmp = os.path.join(MEDIA, "problems", "_alabama_written_combined_tmp.pdf")
                word_to_pdf(app, os.path.join(src_dir, WRITTEN_COMBINED), tmp)
                split_written(tmp, abspath["w1"], abspath["w2"])
                os.remove(tmp)
                print(f"  + split written test -> {targets['w1']}, {targets['w2']}")
            if not is_pdf(abspath["fa"]):
                word_to_pdf(app, os.path.join(src_dir, FIRST_AID_WRITTEN), abspath["fa"])
                print(f"  + converted first-aid written test -> {targets['fa']}")
        finally:
            app.Quit()

    for key in targets:
        if not is_pdf(abspath[key]):
            raise RuntimeError(f"target {key} is not a valid PDF: {targets[key]}")
    return targets


def ingest(do_write):
    event = CalendarEvent.objects.get(title=EVENT_TITLE, start_date__year=YEAR)
    src_dir = os.path.join(ONEDRIVE, FOLDER)
    print(f"### {COMP_NAME} ({YEAR})  ->  event #{event.pk} "
          f"({event.start_date}, {event.location})")

    targets = build_media(src_dir, do_write)

    # (problem title, sort_order, [(doc title, target key, doc sort_order)])
    structure = [
        ("First Aid & Benchman Day 1", 10, [("Field", "field1", 10)]),
        ("First Aid & Benchman Day 2", 20, [("Field", "field2", 10)]),
        ("Written Tests", 30, [
            ("Mine Rescue Written Test - Day 1", "w1", 10),
            ("Mine Rescue Written Test - Day 2", "w2", 20),
            ("First Aid Written Test", "fa", 30),
        ]),
    ]

    n_prob = n_doc = n_skip = 0
    comp = None
    if do_write:
        comp, _ = Competition.objects.get_or_create(
            name=COMP_NAME, year=YEAR, defaults={"calendar_event": event})
        if comp.calendar_event_id != event.pk:
            comp.calendar_event = event
            comp.save(update_fields=["calendar_event"])

    for ptitle, psort, docs in structure:
        print(f"  - {ptitle} ({len(docs)} docs)")
        prob = None
        if do_write:
            prob, _ = CompetitionProblem.objects.get_or_create(
                competition=comp, title=ptitle, defaults={"sort_order": psort})
        n_prob += 1
        for dtitle, key, dsort in docs:
            rel = targets[key]
            if do_write and prob.documents.filter(file=rel).exists():
                n_skip += 1
                print(f"      = {dtitle}  (already present)")
                continue
            if do_write:
                ProblemDocument.objects.get_or_create(
                    problem=prob, file=rel,
                    defaults={"title": dtitle, "sort_order": dsort})
            n_doc += 1
            print(f"      + {dtitle}  ->  {rel}")

    flag = "" if do_write else "  [DRY-RUN]"
    print(f"\n===== {'WROTE' if do_write else 'PLANNED'}{flag}: 1 competition, "
          f"{n_prob} problems, {n_doc} docs"
          + (f", {n_skip} already present" if n_skip else "") + " =====")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ingest(do_write=not args.dry_run)
