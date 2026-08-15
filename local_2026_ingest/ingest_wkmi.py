"""Ingest the 2026 WKMI (Western Kentucky Mine Institute Safety Days) contest.

Same pattern as ``ingest_kmi.py``: each document's source path is given relative
to the competition folder and the target media filename uses the slugified
basename under ``{year}_{anchor}_{problem_slug}_{stem}.ext``.

WKMI is Coal, single division, with five problems: Coal Field, First Aid, Bench
(BioPak 240-R), Preshift, and a consolidated Written Tests. Links to the existing
2026 calendar event "Western Kentucky Mine Institute Safety Days Mine Rescue
Contest" (Madisonville, KY).

Office files (.docx/.doc) are copied as-is; run
``miningquiz_ingest/convert_docs.py`` afterwards to turn them into byte-checked
PDFs so they preview in-browser.

Idempotent: a (problem, file) row is skipped when present and a media file is
only copied when missing — safe to re-run.

Run:  python local_2026_ingest/ingest_wkmi.py        (use --dry-run to preview)
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

SPEC = [
    {
        "folder": "Western Kentucky Mine Institute Safety Days Mine Rescue Contest",
        "name": "Western Kentucky Mine Institute Safety Days Mine Rescue Contest",
        "event_title": "Western Kentucky Mine Institute Safety Days Mine Rescue Contest",
        "anchor": "WKMI",
        "problems": [
            ("Coal Field", [
                ("Field", "WKMI 26.pdf"),
                ("Field (B&W scan)", "2026 KMI.pdf"),
            ]),
            ("First Aid", [
                ("Statement", "2026  WKMI First Aid Statement.docx"),
                ("Pokey - Injuries", "2026 First aid victim Pokey.docx"),
                ("Pokey - Triage", "POKEY Triage.docx"),
                ("Pokey - Skill Sheets", "POKEY Skill Sheets.docx"),
                ("Smokey - Injuries", "2026 First aid victim Smokey - Copy.docx"),
                ("Smokey - Triage", "SMOKEY Traige.docx"),
                ("Smokey - Skill Sheets", "SMOKEY Skill Sheets.docx"),
                ("Envelope #2", "2026 WKMI Envelope #2.docx"),
                ("Envelope #3", "2026 WKMI Envelope #3.docx"),
                ("Labels", "WKMI Labels.doc"),
                ("A Card", "2024 FA Card A.pdf"),
                ("B Card", "2024 FA Card B.pdf"),
            ]),
            ("Bench", [
                ("BioPak 240-R Judge Check Sheet", "BioPak240R Judges Check Sheet.docx"),
            ]),
            ("Preshift", [
                ("Judge's Training", "Preshift Contest Judge's Training.pdf"),
            ]),
            ("Written Tests", [
                ("First Aid Written Test", "2026 WKMI First Aid Test.docx"),
                ("First Aid Written Test Answer Key", "2026 WKMI First Aid Test Answer Key.docx"),
                ("First Aid Written Test (with references)", "First Aid Test.pdf"),
                ("Benchman Written Test (BioPak 240-R)", "Benchman Test.pdf"),
                ("Preshift Written Exam", "Written Exam.pdf"),
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
