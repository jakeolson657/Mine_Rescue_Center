"""Ingest the 2026 NMRA Post 5 and Northern Mine Rescue Association contests.

Same idempotent ORM pattern as ``ingest_kmi.py``: each document's source path is
given relative to the competition folder and the target media filename is
``{year}_{anchor}_{problem_slug}_{stem}.ext`` (slugified). Both contests are Coal,
single division, day-split field problems (mirrors the 2024 Post 5 structure:
Coal Day 1/2 Field).

Unlike ingest_kmi.py, events are resolved **by pk** (Post 5's calendar title
differs from the competition name, and the Northern event shares no distinctive
word for title matching):
  - NMRA Post 5 Mine Rescue Contest        -> CalendarEvent 401 (Morgantown, WV)
  - Northern Mine Rescue Association Comp.  -> CalendarEvent 8   (Cadiz, OH)

The nine NMRA Post 5 *results* PDFs are not problems; they are copied into
media/problems/ and linked on CalendarEvent 401's ``resources`` (local-media
style, like event 61 / Harlan).

Idempotent: a (problem, file) row is skipped when present, a media file is only
copied when missing, and a resource link is only appended when its url is absent.

Run:  local_2026_ingest/ingest_post5_northern.py        (use --dry-run to preview)
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
        "folder": "NMRA Post 5 Mine Rescue Competition",
        "name": "NMRA Post 5 Mine Rescue Contest",
        "event_pk": 401,
        "anchor": "Post_5",
        "problems": [
            ("Coal Day 1 Field", [
                ("Field", "2026 post 5 day 1 packet.pdf"),
            ]),
            ("Coal Day 2 Field", [
                ("Field", "2026 post 5 day 2 packet.pdf"),
            ]),
        ],
        # Results PDFs -> CalendarEvent.resources (label, source filename).
        "event_resources": [
            ("Day 1 Mine Rescue Results", "Day 1 MR_NMRA Post 5_07.28.26.pdf"),
            ("Day 2 Mine Rescue Results", "Day 2 MR_NMRA Post 5_07.29.26.pdf"),
            ("Overall Mine Rescue Results", "Day 2 MR Overall_NMRA Post 5_07.29.26.pdf"),
            ("First Aid Results", "Day 3 First Aid_NMRA Post 5_07.30.26.pdf"),
            ("Preshift Results", "Day 3 Preshift_NMRA Post 5_07.30.26.pdf"),
            ("Draeger BG 4 Bench Results", "Day 3 BG4_NMRA Post 5_07.30.26.pdf"),
            ("Draeger BG ProAir Bench Results", "Day 3 ProAir_NMRA Post 5_07.30.26.pdf"),
            ("BioPak 240R Bench Results", "Day 3 BioPak 240R_NMRA Post 5_07.30.26.pdf"),
            ("Two-Day Combination Results", "Day 3 Two Day Combo Results_NMRA Post 5_07.30.26.pdf"),
        ],
    },
    {
        "folder": "Northern Mine Rescue Association Competition",
        "name": "Northern Mine Rescue Association Competition",
        "event_pk": 8,
        "anchor": "Northern",
        "problems": [
            ("Coal Day 1 Field", [
                ("Field", "Northern Regional Day 1 2026.pdf"),
            ]),
            ("Coal Day 2 Field", [
                ("Field", "Northern Regional Day 2 2026.pdf"),
            ]),
        ],
    },
]


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(anchor, problem_slug, fname):
    stem, ext = os.path.splitext(os.path.basename(fname))
    return f"{slugify(f'{YEAR}_{anchor}_{problem_slug}_{stem}')}{ext.lower()}"


def copy_media(src, rel, do_write):
    dst = os.path.join(MEDIA, rel)
    if do_write and not os.path.exists(dst):
        shutil.copy2(src, dst)


def ingest(do_write):
    os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)
    n_comp = n_prob = n_doc = n_skip = n_res = 0
    for c in SPEC:
        event = CalendarEvent.objects.get(pk=c["event_pk"])
        src_dir = os.path.join(ONEDRIVE, c["folder"])
        print(f"\n### {c['name']}  ->  event #{event.pk} ({event.start_date}, {event.location})")
        comp = None
        if do_write:
            comp, _ = Competition.objects.get_or_create(
                name=c["name"], year=YEAR,
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
                rel = f"problems/{safe_filename(c['anchor'], pslug, fname)}"
                if do_write and prob.documents.filter(file=rel).exists():
                    n_skip += 1
                    print(f"      = {dtitle}  (already present)")
                    continue
                copy_media(src, rel, do_write)
                if do_write:
                    ProblemDocument.objects.get_or_create(
                        problem=prob, file=rel,
                        defaults={"title": dtitle, "sort_order": (di + 1) * 10},
                    )
                n_doc += 1
                print(f"      + {dtitle}  ->  {rel}")

        # Results PDFs -> event.resources (local-media links).
        resources = c.get("event_resources", [])
        if resources:
            existing = list(event.resources or [])
            urls = {r.get("url") for r in existing}
            print(f"  resources -> event #{event.pk} ({len(resources)} results PDFs)")
            for label, fname in resources:
                src = os.path.join(src_dir, fname)
                if not os.path.exists(src):
                    print(f"      !! MISSING SOURCE: {fname}")
                    continue
                rel = f"problems/{safe_filename(c['anchor'], 'Results', fname)}"
                url = f"/media/{rel}"
                if url in urls:
                    print(f"      = {label}  (already linked)")
                    continue
                copy_media(src, rel, do_write)
                existing.append({"label": label, "url": url})
                urls.add(url)
                n_res += 1
                print(f"      + {label}  ->  {url}")
            if do_write:
                event.resources = existing
                event.save(update_fields=["resources"])

    flag = "" if do_write else "  [DRY-RUN]"
    print(f"\n===== {'WROTE' if do_write else 'PLANNED'}{flag}: {n_comp} competitions, "
          f"{n_prob} problems, {n_doc} docs, {n_res} resources"
          + (f", {n_skip} already present" if n_skip else "") + " =====")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ingest(do_write=not args.dry_run)
