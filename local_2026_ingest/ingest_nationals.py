"""Ingest the 2026 National Mine Rescue Contest problems the organizer shared.

Creates the competition (linked to the existing 2026 National calendar event,
which the name-matcher can't reach on its own because every word in the contest
name is a match stopword) and files the four PDFs into the standard form: one
``Coal Day N Field`` problem per contest day holding that day's judges packet,
plus a single ``Written Tests`` problem holding both days' written exams.

Idempotent: problems and documents are matched on title, and a media file is
only copied when missing — safe to re-run.

Run:  python local_2026_ingest/ingest_nationals.py   (use --dry-run to preview)
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
FOLDER = r"C:\Users\Jacob\Downloads\[EXTERNAL] Problems"
YEAR = 2026
ANCHOR = "national"
COMP = "National Mine Rescue Contest"
EVENT_PK = 23  # 2026 National ... Competition, Sevierville TN, 2026-08-24

# problem title -> (sort_order, [(document title, source filename, sort_order)])
PROBLEMS = [
    ("Coal Day 1 Field", 10, [
        ("Field", "26 Nationals Day 1.pdf", 10),
    ]),
    ("Coal Day 2 Field", 20, [
        ("Field", "26 Nationals Day 2.pdf", 10),
    ]),
    ("Written Tests", 30, [
        ("Day 1 Written Test", "26 Nationals Day 1 Written.pdf", 10),
        ("Day 2 Written Test", "26 Nationals Day 2 Written.pdf", 20),
    ]),
]


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def run(do_write):
    event = CalendarEvent.objects.get(pk=EVENT_PK)
    comp = Competition.objects.filter(name=COMP, year=YEAR).first()
    if comp is None:
        print(f"[comp] create {COMP} ({YEAR}) -> event {event.pk} {event.title!r}")
        if do_write:
            comp = Competition(name=COMP, year=YEAR, calendar_event=event)
            comp.save()
    else:
        print(f"[comp] exists pk={comp.pk}")

    for ptitle, psort, docs in PROBLEMS:
        pslug = slugify(ptitle)
        problem = None
        if comp is not None:
            problem = comp.problems.filter(title=ptitle).first()
        if problem is None:
            print(f"  [problem] create {ptitle!r} (sort {psort})")
            if do_write:
                problem = CompetitionProblem.objects.create(
                    competition=comp, title=ptitle, sort_order=psort)
        else:
            print(f"  [problem] exists pk={problem.pk} {ptitle!r}")

        for dtitle, fname, dsort in docs:
            src = os.path.join(FOLDER, fname)
            if not os.path.exists(src):
                raise SystemExit(f"missing source file: {src}")
            target = safe_filename(pslug, fname)
            dst = os.path.join(MEDIA, "problems", target)
            if os.path.exists(dst):
                print(f"    [file] exists {target}")
            else:
                print(f"    [file] copy  {fname} -> {target}")
                if do_write:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

            existing = None
            if problem is not None:
                existing = problem.documents.filter(title=dtitle).first()
            if existing is None:
                print(f"    [doc]  create {dtitle!r} (sort {dsort})")
                if do_write:
                    ProblemDocument.objects.create(
                        problem=problem, title=dtitle,
                        file=f"problems/{target}", sort_order=dsort)
            else:
                print(f"    [doc]  exists pk={existing.pk} {dtitle!r}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(do_write=not args.dry_run)
    print("dry run — nothing written" if args.dry_run else "done")
