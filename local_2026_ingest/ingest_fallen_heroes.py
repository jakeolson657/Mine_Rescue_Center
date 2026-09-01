"""Ingest the 2025 and 2026 Fallen Heroes Mine Rescue Contests.

Both years' materials arrived together in the ``2026/Fallen Heroes`` folder as
legacy PowerPoint decks. The two decks named "... 2025" are the 2025 contest
(Chief Logan, Sept 16-18 2025); the three saved in May/June 2026 -- including the
pre-shift deck, which is explicitly "(2026)" and set at "Chief Logan #1 mine" --
are the 2026 contest (Aug 10-14 2026). Confirmed with the site owner.

The decks were converted to PDF with PowerPoint (SaveAs format 32) and the
converted files live beside the .ppt originals in the source folder, the same way
the Northern written tests were handled. Following the WVU Bench Bash precedent,
the 18-page pre-shift deck was split so its written exam does not stay buried
inside the pre-shift problem: pages 6-7 (the exam) and 8-9 (the answer key)
became their own PDFs and the pre-shift problem keeps the remaining 14 pages.

Both contests are Coal (the established Fallen Heroes type), single division,
day-split field problems -- matching the 2022/2023 entries.

Events are resolved by pk, since "Fallen Heroes Mine Rescue Contest" recurs every
year and the matcher only disambiguates within a year:
  - 2025 -> CalendarEvent 87 (Chief Logan Conference Center, Logan, WV)
  - 2026 -> CalendarEvent 22 (Chief Logan Conference Center, Logan, WV)

Same idempotent ORM pattern / filename convention as ingest_post5_northern.py: a
(problem, file) row is skipped when present and a media file is only copied when
missing.

Run:  local_2026_ingest/ingest_fallen_heroes.py        (--dry-run to preview)
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
           r"\Mine Rescue Center\Past Problems\2026\Fallen Heroes")
NAME = "Fallen Heroes Mine Rescue Contest"
ANCHOR = "Fallen_Heroes"

SPEC = [
    {
        "year": 2025,
        "event_pk": 87,
        "problems": [
            ("Coal Day 1 Field", [
                ("Field", "2025 Fallen Heroes Day 1 Competition.pdf", 10),
            ]),
            ("Coal Day 2 Field", [
                ("Field", "2025 Fallen Heroes Day 2 Competition.pdf", 10),
            ]),
        ],
    },
    {
        "year": 2026,
        "event_pk": 22,
        "problems": [
            ("Coal Day 1 Field", [
                ("Field", "2026 Fallen Heroes Day 1 Competition.pdf", 10),
            ]),
            ("Coal Day 2 Field", [
                ("Field", "2026 Fallen Heroes Day 2 Competition.pdf", 10),
            ]),
            ("Preshift", [
                ("Problem", "2026 Fallen Heroes Pre-Shift Problem.pdf", 10),
            ]),
            # The key sorts directly under its own test (ordering is sort_order,
            # then title), matching the Northern written-test layout.
            ("Written Tests", [
                ("Pre-Shift Written Test", "2026 Fallen Heroes Pre-Shift Written Test.pdf", 10),
                ("Pre-Shift Written Test Key", "2026 Fallen Heroes Pre-Shift Written Test Key.pdf", 15),
            ]),
        ],
    },
]


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(year, problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{year}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def copy_media(src, rel, do_write):
    dst = os.path.join(MEDIA, rel)
    if do_write and not os.path.exists(dst):
        shutil.copy2(src, dst)


def ingest(do_write):
    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)
    n_comp = n_prob = n_doc = n_skip = 0
    for c in SPEC:
        event = CalendarEvent.objects.get(pk=c["event_pk"])
        print(f"\n### {c['year']} {NAME}  ->  event #{event.pk} "
              f"({event.start_date}, {event.location})")
        comp = None
        if do_write:
            comp, _ = Competition.objects.get_or_create(
                name=NAME, year=c["year"], defaults={"calendar_event": event},
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
            for dtitle, fname, dsort in docs:
                src = os.path.join(SRC_DIR, fname)
                if not os.path.exists(src):
                    print(f"      !! MISSING SOURCE: {fname}")
                    continue
                rel = f"problems/{safe_filename(c['year'], pslug, fname)}"
                if do_write and prob.documents.filter(file=rel).exists():
                    n_skip += 1
                    print(f"      = {dtitle}  (already present)")
                    continue
                copy_media(src, rel, do_write)
                if do_write:
                    ProblemDocument.objects.get_or_create(
                        problem=prob, file=rel,
                        defaults={"title": dtitle, "sort_order": dsort},
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
