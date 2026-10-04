"""Add the 2026 ACNR company mine rescue contest.

Six files arrived in ``Downloads/ACNR company contest``, all titled "2026
Foresight" (Foresight Energy, an ACNR company), Coal:

  Foresight 2026 MR D1 Prob.pdf ................ Day 1 map (Maverick Mine)
  Foresight 2026 D1 Statement.docx ............. Day 1 problem statement
  2026 Foresight Day 1 Written Instructions.docx Day 1 written instructions
  Foresight 2026 MR D2 Prob.pdf ................ Day 2 map (Heritage Two Mine)
  Foresight MR D2 26 Statement.docx ............ Day 2 problem statement
  2026 Foresight Day 2 Written Instructions.docx Day 2 written instructions

The four .docx files were converted to PDF beside the originals (Word
filtered-HTML, then headless Edge print) with their content unchanged.

The contest date wasn't supplied. The user asked for it to list as the most
recent 2026 contest, so it gets a placeholder single-day CalendarEvent on
2026-09-30 (after Nationals, Aug 24-27). Correct the event in the admin once
the real date is known.

Idempotent, same as the other ingests: rows already present are skipped and a
media file is only copied when missing.

Run:  local_2026_ingest/ingest_acnr.py     (--dry-run to preview)
"""
import argparse
import datetime
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
SRC_DIR = r"C:\Users\Jacob\Downloads\ACNR company contest"
NAME = "ACNR Company Mine Rescue Contest"
YEAR = 2026
ANCHOR = "ACNR"
EVENT_DATE = datetime.date(2026, 9, 30)  # placeholder, see docstring

PROBLEMS = [
    ("Coal Day 1 Field", 10),
    ("Coal Day 2 Field", 20),
]

DOCS = {
    "Coal Day 1 Field": [
        ("Field", "Foresight 2026 MR D1 Prob.pdf", 10),
        ("Problem Statement", "Foresight 2026 D1 Statement.pdf", 20),
        ("Written Instructions", "2026 Foresight Day 1 Written Instructions.pdf", 30),
    ],
    "Coal Day 2 Field": [
        ("Field", "Foresight 2026 MR D2 Prob.pdf", 10),
        ("Problem Statement", "Foresight MR D2 26 Statement.pdf", 20),
        ("Written Instructions", "2026 Foresight Day 2 Written Instructions.pdf", 30),
    ],
}


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def ingest(do_write):
    event = CalendarEvent.objects.filter(title=NAME, start_date__year=YEAR).first()
    if event is None:
        print(f"+ event {NAME!r} on {EVENT_DATE}")
        if do_write:
            event = CalendarEvent.objects.create(
                title=NAME, start_date=EVENT_DATE, end_date=EVENT_DATE,
                location="",
            )
    else:
        print(f"= event #{event.pk} {event}")

    comp = Competition.objects.filter(name=NAME, year=YEAR).first()
    if comp is None:
        print(f"+ competition {NAME!r} ({YEAR})")
        if do_write:
            comp = Competition.objects.create(
                name=NAME, year=YEAR, calendar_event=event,
            )
    else:
        print(f"= competition #{comp.pk}")

    for title, sort_order in PROBLEMS:
        prob = comp and CompetitionProblem.objects.filter(competition=comp, title=title).first()
        if prob is None:
            print(f"  + problem {title!r} (sort_order {sort_order})")
            if do_write:
                CompetitionProblem.objects.create(
                    competition=comp, title=title, sort_order=sort_order,
                )
        else:
            print(f"  = problem {title!r}")

    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)
    n_doc = n_skip = 0
    for ptitle, docs in DOCS.items():
        prob = comp and CompetitionProblem.objects.filter(competition=comp, title=ptitle).first()
        if prob is None and do_write:
            raise SystemExit(f"problem {ptitle!r} missing after the problem pass")
        print(f"  - {ptitle}")
        pslug = slugify(ptitle)
        for dtitle, fname, dsort in docs:
            src = os.path.join(SRC_DIR, fname)
            if not os.path.exists(src):
                print(f"      !! MISSING SOURCE: {fname}")
                continue
            rel = f"problems/{safe_filename(pslug, fname)}"
            if prob and prob.documents.filter(file=rel).exists():
                n_skip += 1
                print(f"      = {dtitle}  (already present)")
                continue
            dst = os.path.join(MEDIA, rel)
            if do_write and not os.path.exists(dst):
                shutil.copy2(src, dst)
            if do_write:
                ProblemDocument.objects.get_or_create(
                    problem=prob, file=rel,
                    defaults={"title": dtitle, "sort_order": dsort},
                )
            n_doc += 1
            print(f"      + {dtitle}  ->  {rel}")

    flag = "" if do_write else "  [DRY-RUN]"
    print(f"\n===== {'WROTE' if do_write else 'PLANNED'}{flag}: {n_doc} docs"
          + (f", {n_skip} already present" if n_skip else "") + " =====")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ingest(do_write=not args.dry_run)
