"""Add the Written Tests problem to the 2026 Northern Mine Rescue Association
Competition (Competition pk 404).

The contest already has its two field problems (Coal Day 1/2 Field) from
``ingest_post5_northern.py``. This adds a third problem, "Written Tests" (the same
grouping the older Northern contests use), holding the two Day 1/Day 2 mine-rescue
written-test PDFs.

IMPORTANT day labelling: the source docx filenames and their printed headers
disagree. Per the site owner, the PRINTED header is authoritative, so the 32-q
test titled "Day 1" and the 30-q test titled "Day 2" are used as-is (the PDFs in
the source folder are already named that way). The interactive quizzes are built
separately by ``build_northern_written_quizzes.py`` from the answer-key docx.

Same idempotent ORM pattern / filename convention as ingest_post5_northern.py.

Run:  local_2026_ingest/ingest_northern_written.py        (--dry-run to preview)
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
from pages.models import Competition, CompetitionProblem, ProblemDocument  # noqa: E402

MEDIA = settings.MEDIA_ROOT
SRC_DIR = (r"C:\Users\Jacob\OneDrive - Colorado School of Mines\Documents"
           r"\Mine Rescue Center\Past Problems\2026"
           r"\Northern Mine Rescue Association Competition\Written Tests")
YEAR = 2026
ANCHOR = "Northern"
COMP_PK = 404

PROBLEM_TITLE = "Written Tests"
PROBLEM_SORT = 30  # after Coal Day 1 (10) / Coal Day 2 (20)
DOCS = [
    # (doc title, source filename, sort_order)
    ("Day 1 Written Test", "2026 Northern Regional Day 1 Written Test.pdf", 10),
    ("Day 2 Written Test", "2026 Northern Regional Day 2 Written Test.pdf", 20),
]


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def ingest(do_write):
    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)
    comp = Competition.objects.get(pk=COMP_PK)
    print(f"### {comp.name} ({comp.year})  [pk {comp.pk}]")

    prob = None
    if do_write:
        prob, created = CompetitionProblem.objects.get_or_create(
            competition=comp, title=PROBLEM_TITLE,
            defaults={"sort_order": PROBLEM_SORT},
        )
        print(f"  {'+' if created else '='} problem {PROBLEM_TITLE!r} (pk {prob.pk})")
    else:
        print(f"  problem {PROBLEM_TITLE!r} (dry-run)")

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
