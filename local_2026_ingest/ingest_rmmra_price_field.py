"""Add the 2026 Rocky Mountain (Price, Utah) field problems.

Two scans arrived in ``2026/Rocky Mountain Mine Rescue Price Utah``, both
image-only (no text layer), named by the scanner:

  20260629141250871.pdf .. Day 1, 10 pages: written statement, VENT 1, VENT 2,
                           VENT 3, two handwritten "Signal Peak Attendant Map"
                           pages, the marked-up (red) VENT 1, the Judges Map,
                           Gas Extents, and a blank scanner page.
  20260629141530732.pdf .. Day 2, 4 pages: written statement, VENT 3, Vent 4
                           and a (very faint) judges map.

Day 1 is trimmed to the organizers' seven pages -- ``2026 Price Utah Day 1
Field.pdf``, beside the original in the source folder -- dropping the blank
page and the two attendant-map pages, which are a team's own completed map
rather than contest material (user's call, 2026-09-17). Day 2 is archived
exactly as scanned.

They join the existing 2026 competition (#367, which so far holds only the BG4
written test) as ``Coal Day 1 Field`` / ``Coal Day 2 Field``, the same shape the
2017-2022 Price contests use, each with a single ``Field`` document.

Idempotent, same as the other ingests: a (problem, file) row is skipped when
already present and a media file is only copied when missing.

Run:  local_2026_ingest/ingest_rmmra_price_field.py     (--dry-run to preview)
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
    Competition, CompetitionProblem, ProblemDocument,
)

MEDIA = settings.MEDIA_ROOT
SRC_DIR = (r"C:\Users\Jacob\OneDrive - Colorado School of Mines\Documents"
           r"\Mine Rescue Center\Past Problems\2026"
           r"\Rocky Mountain Mine Rescue Price Utah")
NAME = "50th Annual Rocky Mountain Mine Rescue Association Contest"
YEAR = 2026
ANCHOR = "RMMRC_Price"

# Field days sort ahead of the written tests already on the competition
# (sort_order 40).
PROBLEMS = [
    ("Coal Day 1 Field", 10),
    ("Coal Day 2 Field", 20),
]

NEW_DOCS = {
    "Coal Day 1 Field": [
        ("Field", "2026 Price Utah Day 1 Field.pdf", 10),
    ],
    "Coal Day 2 Field": [
        # As scanned; the scanner name is replaced on the way into media/.
        ("Field", "20260629141530732.pdf", 10),
    ],
}

# The scanner names carry nothing, so the media filenames are spelled out.
MEDIA_STEM = {
    "20260629141530732.pdf": "2026 Price Utah Day 2 Field",
}


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    stem = MEDIA_STEM.get(os.path.basename(fname), stem)
    return f"{slugify(f'{YEAR}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def ingest(do_write):
    comp = Competition.objects.get(name=NAME, year=YEAR)
    print(f"### {comp}  (competition #{comp.pk})")

    for title, sort_order in PROBLEMS:
        prob = CompetitionProblem.objects.filter(competition=comp, title=title).first()
        if prob is None:
            print(f"  + problem {title!r} (sort_order {sort_order})")
            if do_write:
                CompetitionProblem.objects.create(
                    competition=comp, title=title, sort_order=sort_order,
                )
        else:
            print(f"  = problem {title!r} (sort_order {prob.sort_order})")

    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)
    n_doc = n_skip = 0
    for ptitle, docs in NEW_DOCS.items():
        prob = CompetitionProblem.objects.filter(competition=comp, title=ptitle).first()
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
            if prob is not None and prob.documents.filter(file=rel).exists():
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
