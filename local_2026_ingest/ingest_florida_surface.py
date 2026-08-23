"""Ingest the 2025 Florida Surface Mining Emergency Response Training Competition.

The source folder is filed under ``Past Problems/2026/7th Annual Surface Mining
Emergency Response Training Competition``, but every document inside is from the
**2025** running of the contest ("2025 FLORIDA SURFACE MINE RESCUE CONTEST" on
each cover page; the results PDF is headed "Havana, Florida / Feb 24 - 27, 2025").
Per the site owner the papers win, so this ingests a 2025 competition linked to
CalendarEvent 68 (Feb 24-27 2025, Florida Public Safety Institute, Havana FL).

Every document is a written test, so the contest gets a single ``Written Tests``
problem holding all six PDFs, with each answer key sort-ordered directly under
its own test (same shape as the 2026 Northern written tests). Note the
"Regional Field Competition Test" is itself a written (Brady-book) exam despite
its name -- there is no field problem in this packet.

The organizers supplied .docx files; they were converted to PDF (content
unchanged, see [[preserve-organizer-documents]]) into the folder's ``PDF``
subdirectory, which is what this script reads.

The one non-test document, ``2025 Florida MR Results.pdf``, is NOT ingested:
CalendarEvent 68 already links MSHA's copy of that exact file under
"Mine Rescue and First Aid Results".

Same idempotent ORM pattern / filename convention as ingest_post5_northern.py.

Run:  local_2026_ingest/ingest_florida_surface.py        (--dry-run to preview)
"""
import argparse
import os
import re
import shutil
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

MEDIA = settings.MEDIA_ROOT
SRC_DIR = (r"C:\Users\Jacob\OneDrive - Colorado School of Mines\Documents"
           r"\Mine Rescue Center\Past Problems\2026"
           r"\7th Annual Surface Mining Emergency Response Training Competition"
           r"\PDF")
YEAR = 2025
ANCHOR = "Florida_Surface"
COMP_NAME = "Surface Mining Emergency Response Training Competition"
EVENT_PK = 68

PROBLEM_TITLE = "Written Tests"
PROBLEM_SORT = 10
# sort_order puts each answer key directly under its own test (the model orders
# by sort_order, then title).
DOCS = [
    # (doc title, source filename, sort_order)
    ("Regional Field Competition Test",
     "2025 Florida Surface Regional Field Competition Test.pdf", 10),
    ("Regional Field Competition Test Key",
     "2025 Florida Surface Regional Field Competition Test Key.pdf", 15),
    ("First Aid Written Test",
     "2025 Florida Surface First Aid Written Test.pdf", 20),
    ("First Aid Written Test Key",
     "2025 Florida Surface First Aid Written Test Key.pdf", 25),
    ("Team Trainer Test",
     "2025 Florida Surface Team Trainer Test.pdf", 30),
    ("Team Trainer Test Key",
     "2025 Florida Surface Team Trainer Test Key.pdf", 35),
]


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def ingest(do_write):
    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)
    event = CalendarEvent.objects.get(pk=EVENT_PK)
    print(f"### {COMP_NAME} ({YEAR})  ->  event #{event.pk} "
          f"({event.start_date}, {event.location})")

    comp = prob = None
    if do_write:
        comp, created = Competition.objects.get_or_create(
            name=COMP_NAME, year=YEAR, defaults={"calendar_event": event},
        )
        if comp.calendar_event_id != event.pk:
            comp.calendar_event = event
            comp.save(update_fields=["calendar_event"])
        print(f"  {'+' if created else '='} competition (pk {comp.pk})")
        prob, created = CompetitionProblem.objects.get_or_create(
            competition=comp, title=PROBLEM_TITLE,
            defaults={"sort_order": PROBLEM_SORT},
        )
        print(f"  {'+' if created else '='} problem {PROBLEM_TITLE!r} (pk {prob.pk})")
    else:
        print(f"  competition + problem {PROBLEM_TITLE!r} (dry-run)")

    pslug = slugify(PROBLEM_TITLE)
    n_doc = n_skip = 0
    for dtitle, fname, sort in DOCS:
        src = os.path.join(SRC_DIR, fname)
        if not os.path.exists(src):
            print(f"      !! MISSING SOURCE: {fname}")
            continue
        rel = f"problems/{safe_filename(pslug, fname)}"
        if do_write and prob.documents.filter(file=rel).exists():
            n_skip += 1
            print(f"      = {dtitle}  (already present)  ->  {rel}")
            continue
        dst = os.path.join(MEDIA, rel)
        if do_write and not os.path.exists(dst):
            shutil.copy2(src, dst)
        if do_write:
            doc, _ = ProblemDocument.objects.get_or_create(
                problem=prob, file=rel,
                defaults={"title": dtitle, "sort_order": sort},
            )
            print(f"      + {dtitle}  ->  {rel}  (doc pk {doc.pk})")
        else:
            print(f"      + {dtitle}  ->  {rel}")
        n_doc += 1

    flag = "" if do_write else "  [DRY-RUN]"
    print(f"===== {'WROTE' if do_write else 'PLANNED'}{flag}: {n_doc} docs"
          + (f", {n_skip} already present" if n_skip else "") + " =====")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ingest(do_write=not args.dry_run)
