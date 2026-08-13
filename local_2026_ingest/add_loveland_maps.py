"""Add the Visio->PDF map exports the organizer converted after the initial
Loveland 2026 ingest: the four Preshift maps plus each Coal day's Attendant Map
and annotated judges master map. Appends them to the existing problems (higher
sort_order), copies files into media/problems/ under the same safe-filename
convention. Idempotent.

Run:  python local_2026_ingest/add_loveland_maps.py   (use --dry-run to preview)
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
from pages.models import Competition, ProblemDocument  # noqa: E402

MEDIA = settings.MEDIA_ROOT
FOLDER = (r"C:\Users\Jacob\OneDrive - Colorado School of Mines\Documents"
          r"\Mine Rescue Center\Past Problems\2026\Colorado_Regional_Mine_Rescue_Contest")
YEAR = 2026
ANCHOR = "Loveland"
COMP = "Colorado Regional Mine Rescue Contest"

# problem title -> list of (document title, source path relative to FOLDER).
# start_sort is where to begin appending for each problem (after existing docs).
ADDITIONS = {
    "Preshift": (90, [
        ("Contestant Map", r"Loveland Preshift 2026\Contestant map-2016.pdf"),
        ("Field Layout Map", r"Loveland Preshift 2026\Field layout map-2016.pdf"),
        ("Judges Map", r"Loveland Preshift 2026\Judge's Map.pdf"),
        ("Ventilation Plan", r"Loveland Preshift 2026\Ventilation Map - Plan.pdf"),
    ]),
    "Coal Day 1 Field": (170, [
        ("Attendant Map", r"lovelandcoal2026day1adminfilesalongwiththenewests\2026 Loveland COAL day 1 Attendent Map.pdf"),
        ("Judges Master Map", r"lovelandcoal2026day1adminfilesalongwiththenewests\2026 Loveland COAL day 1.pdf"),
    ]),
    "Coal Day 2 Field": (200, [
        ("Attendant Map", r"lovelandday2adminfiles\2026 Loveland COAL day 2 Attendant Map.pdf"),
        ("Judges Master Map", r"lovelandday2adminfiles\2026 Loveland COAL day 2.pdf"),
    ]),
}


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{ANCHOR}_{problem_slug}_{stem}')}{ext.lower()}"


def run(do_write):
    comp = Competition.objects.get(name=COMP, year=YEAR)
    n_doc = n_skip = 0
    for ptitle, (start_sort, docs) in ADDITIONS.items():
        prob = comp.problems.get(title=ptitle)
        pslug = slugify(ptitle)
        print(f"\n### {ptitle}")
        for i, (dtitle, fname) in enumerate(docs):
            src = os.path.join(FOLDER, fname)
            if not os.path.exists(src):
                print(f"   !! MISSING SOURCE: {fname}")
                continue
            rel = f"problems/{safe_filename(pslug, fname)}"
            dst = os.path.join(MEDIA, rel)
            if do_write and prob.documents.filter(file=rel).exists():
                n_skip += 1
                print(f"   = {dtitle} (already present)")
                continue
            if do_write:
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                ProblemDocument.objects.get_or_create(
                    problem=prob, file=rel,
                    defaults={"title": dtitle, "sort_order": start_sort + i * 10},
                )
            n_doc += 1
            print(f"   + {dtitle} [sort {start_sort + i * 10}] -> {rel}")
    print(f"\n===== {'WROTE' if do_write else 'PLANNED'}: {n_doc} docs"
          + (f", {n_skip} already present" if n_skip else "") + " =====")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    run(do_write=not ap.parse_args().dry_run)
