"""Ingest two more 2026 contest folders: the Colorado Regional (Loveland) and
the 38th Annual Indiana contest.

Same idea as ``ingest.py`` but the source files live in per-problem subfolders,
so each document's source path is given relative to the competition folder. The
target media filename always uses just the basename (slugified) under the
project's ``{year}_{anchor}_{problem_slug}_{stem}.ext`` convention.

Office files (.docx/.pptx) are copied as-is; run
``miningquiz_ingest/convert_docs.py`` afterwards to turn them into byte-checked
PDFs so they preview in-browser. Visio (.vsd/.vss) sources are intentionally
left out — nothing converts them and they don't preview.

Idempotent: a (problem, file) row is skipped when present and a media file is
only copied when missing — safe to re-run.

Run:  python local_2026_ingest/ingest_co_in.py        (use --dry-run to preview)
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
ONEDRIVE = r"C:\Users\Jacob\OneDrive - Colorado School of Mines\Documents\Mine Rescue Center\Past Problems\2026"
YEAR = 2026

# Each competition: source folder, name, the 2026 calendar event it links to, a
# short filename anchor, and its problems. Every problem is a title plus an
# ordered list of (document title, source path relative to the folder).
SPEC = [
    {
        "folder": "Colorado_Regional_Mine_Rescue_Contest",
        "name": "Colorado Regional Mine Rescue Contest",
        "event_title": "Colorado Regional Mine Rescue, Bench, Pre-shift, First-Aid and Team Technician Contest",
        "anchor": "Loveland",
        "problems": [
            ("Coal Day 1 Field", [
                ("Problem", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Problem.pdf"),
                ("Written Problem", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Written Problem .pdf"),
                ("Written Statement", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Written Statement .pdf"),
                ("Judges Instructions", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Judges Instructions.pdf"),
                ("Judges Stops/DI/RR/GT Map", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Judges Map stops-di-rr-gt.pdf"),
                ("Judges Vent Map", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Judges Vent Map.pdf"),
                ("Final Vent Plan", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Final Vent Map.pdf"),
                ("Vent Plan 1", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Vent 1.pdf"),
                ("Vent Plan 1 (Alternate)", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Vent 1 ALT.pdf"),
                ("Vent Plan 2", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Vent 2.pdf"),
                ("Layout", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Layout.pdf"),
                ("Team Map", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Large TEAM Map.pdf"),
                ("Team Map Key", "lovelandcoal2026day1files/2026 Loveland COAL day 1 LARGE TRANSPARENT TEAM MAP KEY.pdf"),
                ("Breakdown Map", "lovelandcoal2026day1files/2026 Loveland COAL day 1 Large BO Map.pdf"),
                ("Breakdown Map Key", "lovelandcoal2026day1files/2026 Loveland COAL day 1 LARGE TRANSPARENT BO MAP KEY.pdf"),
                ("Gas Extents", "lovelandcoal2026day1files/2026 Loveland COAL day 1 gas extents.pdf"),
            ]),
            ("Coal Day 2 Field", [
                ("Problem", "loveland2026coalday2files/2026 Loveland COAL day 2 Problem.pdf"),
                ("Written Problem", "loveland2026coalday2files/2026 Loveland COAL day 2 Written Problem.pdf"),
                ("Written Statement", "loveland2026coalday2files/2026 Loveland COAL day 2 Written Statement.pdf"),
                ("Judges Instructions", "loveland2026coalday2files/2026 Loveland COAL day 2 Judges Instructions.pdf"),
                ("Judges Stops/GT/DI Map", "loveland2026coalday2files/2026 Loveland COAL day 2 judges map stops-gt-di.pdf"),
                ("Judges Extra Vent Map", "loveland2026coalday2files/2026 Loveland COAL day 2 Judges Extra Vent Map.pdf"),
                ("Final Vent Plan", "loveland2026coalday2files/2026 Loveland COAL day 2 Final Vent.pdf"),
                ("Vent Plan 1", "loveland2026coalday2files/2026 Loveland COAL day 2 Vent 1.pdf"),
                ("Vent Plan 1 (Alternate)", "loveland2026coalday2files/2026 Loveland COAL day 2 Vent 1 ALT.pdf"),
                ("Vent Plan 2", "loveland2026coalday2files/2026 Loveland COAL day 2 Vent 2.pdf"),
                ("Vent Plan 2 (Alternate)", "loveland2026coalday2files/2026 Loveland COAL day 2 Vent 2 ALT.pdf"),
                ("Vent Plan 3", "loveland2026coalday2files/2026 Loveland COAL day 2 Vent 3.pdf"),
                ("Vent Plan 4", "loveland2026coalday2files/2026 Loveland COAL day 2 Vent 4.pdf"),
                ("Layout", "loveland2026coalday2files/2026 Loveland COAL day 2 Layout.pdf"),
                ("Team Map", "loveland2026coalday2files/2026 Loveland COAL day 2 LARGE TEAM MAP.pdf"),
                ("Team Map Key", "loveland2026coalday2files/2026 Loveland COAL day 2 LARGE TRANSPARENT TEAM MAP KEY.pdf"),
                ("Breakdown Map", "loveland2026coalday2files/2026 Loveland COAL day 2 LARGE BO MAP.pdf"),
                ("Breakdown Map Key", "loveland2026coalday2files/2026 Loveland COAL day 2 LARGE TRANSPARENT BO MAP KEY.pdf"),
                ("Gas Extents", "loveland2026coalday2files/2026 Loveland COAL day 2 gas extents.pdf"),
            ]),
            ("Preshift", [
                ("Statement", "Loveland Preshift 2026/PRESHIFT STATEMENT.docx"),
                ("Measurements", "Loveland Preshift 2026/MEASUREMENTS.docx"),
                ("Placards", "Loveland Preshift 2026/Placards Loveland Preshift 2026.pptx"),
                ("A Card - Field", "Loveland Preshift 2026/2026 Preshift A Card - Field.pdf"),
                ("B Card - Record", "Loveland Preshift 2026/2026 Preshift B Card - Record.pdf"),
                ("Preshift Record Report (Blank)", "Loveland Preshift 2026/2026 PRESHIFT RECORD REPORT - BLANK.pdf"),
                ("Judges Notes", "Loveland Preshift 2026/Judge's Notes.docx"),
                ("Judges Preshift Record Report", "Loveland Preshift 2026/JUDGE'S PRESHIFT RECORD REPORT.pdf"),
            ]),
        ],
    },
    {
        "folder": "38th Annual Indiana Mine Rescue Contest",
        "name": "Indiana State Mine Rescue Contest",
        "event_title": "38th Annual Indiana Mine Rescue Contest",
        "anchor": "Indiana",
        "problems": [
            ("Coal Field", [
                ("Field", "26 problem binder.pdf"),
            ]),
        ],
    },
]


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(anchor, problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{anchor}_{problem_slug}_{stem}')}{ext.lower()}"


def resolve_event(title):
    return CalendarEvent.objects.get(title=title, start_date__year=YEAR)


def ingest(do_write):
    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)
    n_comp = n_prob = n_doc = n_skip = 0
    for c in SPEC:
        event = resolve_event(c["event_title"])
        src_dir = os.path.join(ONEDRIVE, c["folder"])
        print(f"\n### {c['name']}  ->  event #{event.pk} ({event.start_date}, {event.location})")
        comp = None
        if do_write:
            comp, created = Competition.objects.get_or_create(
                name=c["name"],
                year=YEAR,
                defaults={"calendar_event": event},
            )
            if comp.calendar_event_id != event.pk:
                comp.calendar_event = event
                comp.save(update_fields=["calendar_event"])
        n_comp += 1
        for pi, (ptitle, docs) in enumerate(c["problems"]):
            prob = None
            if do_write:
                prob, _ = CompetitionProblem.objects.get_or_create(
                    competition=comp, title=ptitle,
                    defaults={"sort_order": (pi + 1) * 10},
                )
            n_prob += 1
            print(f"  - {ptitle} ({len(docs)} docs)")
            pslug = slugify(ptitle)
            for di, (dtitle, fname) in enumerate(docs):
                src = os.path.join(src_dir, fname)
                if not os.path.exists(src):
                    print(f"      !! MISSING SOURCE: {fname}")
                    continue
                target = safe_filename(c["anchor"], pslug, fname)
                rel = f"problems/{target}"
                dst = os.path.join(MEDIA, rel)
                exists = do_write and prob.documents.filter(file=rel).exists()
                if exists:
                    n_skip += 1
                    print(f"      = {dtitle}  (already present)")
                    continue
                if do_write:
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                    ProblemDocument.objects.get_or_create(
                        problem=prob, file=rel,
                        defaults={"title": dtitle, "sort_order": (di + 1) * 10},
                    )
                n_doc += 1
                print(f"      + {dtitle}  ->  {rel}")
    flag = "" if do_write else "  [DRY-RUN]"
    print(f"\n===== {'WROTE' if do_write else 'PLANNED'}{flag}: {n_comp} competitions, "
          f"{n_prob} problems, {n_doc} docs"
          + (f", {n_skip} already present" if n_skip else "") + " =====")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ingest(do_write=not args.dry_run)
