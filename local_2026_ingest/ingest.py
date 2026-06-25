"""Ingest three 2026 contest folders shared by organizers into the Past
Problems archive.

Unlike miningquiz_ingest (Wayback) this reads local folders the user dropped in
OneDrive. Each competition's files are grouped into problems and copied into
``media/problems/`` under the project's safe-filename convention
(``{year}_{anchor}_{problem_slug}_{stem}.ext`` slugified). Office files
(.docx/.pptx/.xlsx) are copied as-is here; ``miningquiz_ingest/convert_docs.py``
turns them into byte-checked PDFs afterwards (run it right after this).

Idempotent: a (problem, file) row is skipped when it already exists, and a media
file is only copied when missing — safe to re-run.

Run:  python local_2026_ingest/ingest.py        (use --dry-run to preview)
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

# Each competition: the source folder, the name to file it under, the 2026
# calendar event it links to, a short filename anchor, and its problems. Every
# problem is a title plus an ordered list of (document title, source filename).
SPEC = [
    {
        "folder": "53rd Annual Mine Rescue and First Aid Competition - Southern Regional",
        "name": "2026 Southern Regional Mine Rescue Contest",
        "event_title": "53rd Annual Mine Rescue and First Aid Competition - Southern Regional",
        "anchor": "southern",
        "problems": [
            ("Mine Rescue", [
                ("Day 1 Field", "day 1 field Broussard April  2026.pdf"),
                ("Day 1 Solution", "Day one solution  April 28th 2026 New Iberia.pdf"),
                ("Day 2 Field", "Day 2 field broussard April 2026.pdf"),
            ]),
        ],
    },
    {
        "folder": "Post 6 Ohio Valley Mine Rescue Contest",
        "name": "2026 Post 6 Ohio Valley Mine Rescue Contest",
        "event_title": "Post 6 Ohio Valley Mine Rescue Contest",
        "anchor": "Post6",
        "problems": [
            ("Mine Rescue", [
                ("Day 1", "2026 Post 6 Day 1.pdf"),
                ("Day 2", "2026 Post 6 Day 2 Rev1.pdf"),
            ]),
            ("Bench", [
                ("BioPak 240R Judges Packet", "Final BioPak 240R Judges Packet - 2026 Post 6.pdf"),
                ("BioPak 240R Judges Check Sheet", "2026 Post 6 BioPak240R Judges Check Sheet.docx"),
                ("Bench Written Test (240R)", "26 Post 6 Bench Written Test 240R.docx"),
                ("Bench Written Test Answers (240R)", "26 Post 6 Bench Written Test 240R Answers Sheet.docx"),
                ("Parts Test", "26 Post 6 Parts Test.docx"),
                ("Parts Answers Sheet", "26 Post 6 Parts Answers Sheet.docx"),
            ]),
        ],
    },
    {
        "folder": "Western_Mine_Rescue_Association_Nevada_Underground_Mine_Rescue_Contest",
        "name": "2026 Western Mine Rescue Association Nevada Underground Mine Rescue Contest",
        "event_title": "Western Mine Rescue Association Nevada UG Mine Rescue Contest",
        "anchor": "WMRA",
        "problems": [
            ("Day 1 Field", [
                ("Field", "01 2026 WMRA Day 1 Field.pptx"),
                ("Maps", "01 2026 WMRA MAPS.pdf"),
                ("Placards", "01 DAY 1 PLACARDS (A).pptx"),
                ("Placard List", "01 D-1 Placard lsit.xlsx"),
            ]),
            ("Day 2 Field", [
                ("Field", "02 2026 WMRA Day 2 Field.pptx"),
                ("Placards", "02 DAY 2 PLACARDS (A).pptx"),
                ("Placard List", "02 D-2 Placard lsit.xlsx"),
            ]),
            ("Written Tests", [
                ("Field Written Test", "2026 WMRA Field Written Test with Answer Sheet.pdf"),
                ("First Aid Written Test", "2026 WMRA First Aid Written Test with Answer Sheet.pdf"),
                ("BG4 Written Test", "2026 WMRA BG4 Written Test with Answer Sheet.pdf"),
                ("BioMarine 240R Written Test", "2026 WMRA BioMarine 240R With Answer Sheet.pdf"),
                ("ProAir Written Test", "2026 WMRA ProAir Written Test with Answer Sheet.pdf"),
                ("Team Technician Written Test", "2026 WMRA Team Technician Test with Answer Sheet.pdf"),
                ("Team Trainer Written Test", "2026 WMRA Team Trainer Test with Answer Sheet.pdf"),
            ]),
        ],
    },
]

YEAR = 2026


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(anchor, problem_slug, fname):
    stem, ext = os.path.splitext(fname)
    return f"{slugify(f'{YEAR}_{anchor}_{problem_slug}_{stem}')}{ext.lower()}"


def resolve_event(title):
    """The 2026 calendar event with this exact title (several contests recur
    across years, so the year filter is what disambiguates)."""
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
                defaults={"year": YEAR, "calendar_event": event},
            )
            if not created and comp.calendar_event_id != event.pk:
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
