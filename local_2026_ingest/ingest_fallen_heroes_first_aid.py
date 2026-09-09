"""Add the 2026 Fallen Heroes first aid materials (the "Part 2" folder).

A second batch of 2026 Fallen Heroes documents arrived in
``2026/Fallen_Heroes_Part2``. Three of its six files are byte-identical (md5)
to decks already ingested by ingest_fallen_heroes.py -- the two "Competition
Problem (Day N)" decks and "Pre-Shift Problem (2026)" -- so only the first aid
material is new:

  - First Aid Problem.pdf ....... the 16-page 2026 First-Aid Competition packet
                                  (cover, two patient-assessment skeletons for
                                  Trevor and Luke, then 13 numbered skill
                                  sheets). Distinct from the 2024 Fallen Heroes
                                  packet already on the site (different md5,
                                  cover reads "2026 First-Aid Competition").
  - First-aid statement 2026.docx ....... the briefing read to teams
  - first-aid written exam 2026.docx .... 15-question first aid written test

The two .docx were converted to PDF with Word (SaveAs 10, filtered HTML) plus
headless Edge --print-to-pdf, the documented fallback for multi-page Word docs,
and the converted PDFs sit beside the originals in the source folder the same
way the .ppt conversions do.

Structure follows the 2026 KMI / WKMI first aid entries: a ``First Aid``
problem holding ``Statement`` then ``Problem``, and the written test folded
into the existing ``Written Tests`` problem. Problem sort_order is renumbered
so First Aid lands before Preshift (the site-wide discipline order: field days,
First Aid, Preshift, Written Tests), and the written tests are reordered to
mirror it.

The written exam ships with no answer key and no marked answers, so it gets no
quiz -- the PDF is archived as-is.

Idempotent, same as the other ingests: a (problem, file) row is skipped when
already present and a media file is only copied when missing.

Run:  local_2026_ingest/ingest_fallen_heroes_first_aid.py     (--dry-run to preview)
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
           r"\Mine Rescue Center\Past Problems\2026\Fallen_Heroes_Part2")
NAME = "Fallen Heroes Mine Rescue Contest"
YEAR = 2026
ANCHOR = "Fallen_Heroes"

# Final problem order for the 2026 contest. The first four already exist; only
# their sort_order changes, to make room for First Aid ahead of Preshift.
PROBLEM_ORDER = [
    ("Coal Day 1 Field", 10),
    ("Coal Day 2 Field", 20),
    ("First Aid", 30),
    ("Preshift", 40),
    ("Written Tests", 50),
]

# New documents, keyed by the problem they belong to.
NEW_DOCS = {
    "First Aid": [
        ("Statement", "2026 Fallen Heroes First Aid Statement.pdf", 10),
        ("Problem", "First Aid Problem.pdf", 20),
    ],
    "Written Tests": [
        ("First Aid Written Test", "2026 Fallen Heroes First Aid Written Test.pdf", 10),
    ],
}

# Existing Written Tests docs move down so the list mirrors the problem order
# (First Aid before Pre-Shift); the key keeps sorting directly under its test.
WRITTEN_TEST_RESORT = {
    "Pre-Shift Written Test": 20,
    "Pre-Shift Written Test Key": 25,
}


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def ingest(do_write):
    comp = Competition.objects.get(name=NAME, year=YEAR)
    print(f"### {comp}  (competition #{comp.pk})")

    # 1. Problem ordering, creating First Aid if it isn't there yet.
    for title, sort_order in PROBLEM_ORDER:
        prob = CompetitionProblem.objects.filter(competition=comp, title=title).first()
        if prob is None:
            print(f"  + problem {title!r} (sort_order {sort_order})")
            if do_write:
                CompetitionProblem.objects.create(
                    competition=comp, title=title, sort_order=sort_order,
                )
        elif prob.sort_order != sort_order:
            print(f"  ~ problem {title!r} sort_order {prob.sort_order} -> {sort_order}")
            if do_write:
                prob.sort_order = sort_order
                prob.save(update_fields=["sort_order"])
        else:
            print(f"  = problem {title!r} (sort_order {sort_order})")

    # 2. Re-sort the written tests already present.
    wt = CompetitionProblem.objects.filter(competition=comp, title="Written Tests").first()
    if wt is not None:
        for doc in wt.documents.all():
            want = WRITTEN_TEST_RESORT.get(doc.title)
            if want is not None and doc.sort_order != want:
                print(f"  ~ doc {doc.title!r} sort_order {doc.sort_order} -> {want}")
                if do_write:
                    doc.sort_order = want
                    doc.save(update_fields=["sort_order"])

    # 3. The new documents.
    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)
    n_doc = n_skip = 0
    for ptitle, docs in NEW_DOCS.items():
        prob = CompetitionProblem.objects.filter(competition=comp, title=ptitle).first()
        if prob is None and do_write:
            raise SystemExit(f"problem {ptitle!r} missing after step 1")
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
