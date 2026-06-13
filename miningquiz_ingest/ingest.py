"""Bulk ingester for the miningquiz.com contest archive (Wayback).

Source: https://miningquiz.com/contests.htm#problems -> per-year archives.

Within a contest section the page is a linear sequence of `<b>Label</b>` groups
(Mine Rescue, First Aid, Bench, Preshift, Written Exam, ...) each followed by a
table of links. Two link styles appear and are both handled:
  * direct file links with descriptive text  -> label = problem, link text = doc
    title (2021-2023, and the legacy years).
  * folder links -> Wayback directory listing -> files (2024; folder = problem,
    filename-derived doc titles).

Noise groups (Media/results/photos, *Resources sidebar, Online Quizzes) and
non-document files (images, html) are filtered out.

Design: read-only Wayback fetches are disk-cached; files are pulled RAW via the
Wayback `id_` form and byte-checked (%PDF / PK) -- see [[wayback-pdf-uploads]].
Idempotent + resumable (a doc is skipped when its media file already exists and
a ProblemDocument points at it). Hand-curated contests in PROTECT are untouched.

Usage:
  python ingest.py --dry-run --year 2023
  python ingest.py --years 2021 2022 2023 2024
"""
import argparse
import hashlib
import html
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from pages.models import Competition, CompetitionProblem, ProblemDocument  # noqa: E402

TS = "20250426140841"
WB = "https://web.archive.org/web/"
SITE = "https://miningquiz.com/"
CTX = ssl.create_default_context()
MEDIA = settings.MEDIA_ROOT
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.join(MEDIA, "problems"), exist_ok=True)

PROTECT = {("2024", "CO_Regional")}  # hand-curated -> never auto-touch
DOWNLOAD_DELAY = 0.3  # polite pause before each file fetch (avoid Wayback throttling)

# `<b>` group labels that are NOT problem content (substring, case-insensitive).
EXCLUDE_LABELS = (
    "media", "resource", "online quiz", "photo", "web site", "website",
    "result", "sponsor", "registration", "schedule", "agenda", "award",
)
DOC_EXTS = (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".rtf")
IMG_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff")

ACRONYMS = {
    "BG4", "MNM", "MR", "BO", "FAB", "CC", "RT", "DI", "GT", "ERP", "BIO", "HV",
    "RA", "PC", "BC", "LC", "CA", "FPA", "SOF", "IMRC", "KMI", "NMRA", "RMMRC",
    "RMMRA", "CMRA", "LOC", "ODNR", "SKCTC", "ALT", "WV", "KY", "PA", "CO",
    "NM", "UT", "NV", "TN", "VA", "IL", "IN", "OH", "AL", "WY", "ID", "KS",
    "MO", "H2S", "CO2", "O2", "II", "III", "BG", "SEMRC",
}

# ----------------------------------------------------------------------------- net


def fetch(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                raise
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2 + 2 * i)
    raise last


def cached(url):
    key = hashlib.sha1(url.encode()).hexdigest() + ".bin"
    path = os.path.join(CACHE, key)
    if os.path.exists(path):
        return open(path, "rb").read()
    data = fetch(url)
    with open(path, "wb") as f:
        f.write(data)
    return data


def wb(orig):
    return f"{WB}{TS}/{orig}"


def wb_raw(ts, orig):
    return f"{WB}{ts}id_/{urllib.parse.quote(orig, safe=':/')}"


# ----------------------------------------------------------------------------- parse


def clean_text(s, sep=" "):
    t = html.unescape(re.sub(r"<[^>]+>", sep, s))
    t = t.replace("\xa0", " ").replace("�", " ")
    return re.sub(r"\s+", " ", t).strip(" ,-—")


def split_sections(page):
    parts = re.split(r'<a name="([^"]+)">', page)
    return [(parts[k], parts[k + 1]) for k in range(1, len(parts) - 1, 2)]


def contest_meta(section):
    name = ""
    mh = re.search(r"<h4>(.*?)(?:<span|</h4>)", section, re.S | re.I)
    if mh:
        name = clean_text(mh.group(1))
    loc = ""
    ms = re.search(r'<span class="reg">(.*?)</span>', section, re.S | re.I)
    if ms:
        loc = clean_text(ms.group(1), sep=", ")
    return name, loc


def section_groups(section, base_orig):
    """Linear walk: [(label, [(text, url, is_folder, is_external)])] per <b> group."""
    parts = re.split(r"<b>(.*?)</b>", section, flags=re.S | re.I)
    groups = []
    for k in range(1, len(parts) - 1, 2):
        label = clean_text(parts[k])
        links = []
        for a in re.finditer(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', parts[k + 1], re.S | re.I):
            # unescape so filenames with & (e.g. "test &amp; answers.doc") resolve
            href, txt = html.unescape(a.group(1)), clean_text(a.group(2))
            if href.startswith(("#", "mailto", "javascript")):
                continue
            external = href.startswith(("http", "/web"))
            is_folder = href.endswith("/") and not external
            url = href if external else urllib.parse.urljoin(base_orig, href)
            links.append((txt, url, is_folder, external))
        groups.append((label, links))
    return groups


def parse_listing(listing_html, folder_orig):
    folder_path = urllib.parse.urlsplit(folder_orig).path
    files, seen = [], set()
    for m in re.finditer(r'href="(/web/\d+/https?://miningquiz\.com/[^"]+)"', listing_html, re.I):
        href = html.unescape(m.group(1))
        orig = re.sub(r"^/web/\d+(?:id_|im_)?/", "", href)
        path = urllib.parse.urlsplit(orig).path
        if not path.startswith(folder_path) or path == folder_path:
            continue
        if href in seen:
            continue
        seen.add(href)
        fname = urllib.parse.unquote(path.rsplit("/", 1)[-1])
        files.append((fname, href, orig))
    return files


def is_excluded(label):
    low = label.lower()
    return any(x in low for x in EXCLUDE_LABELS)


def is_doc(path):
    return path.lower().endswith(DOC_EXTS)


def is_image(path):
    return path.lower().endswith(IMG_EXTS)


# ----------------------------------------------------------------------------- titles


def titlecase(s):
    out = []
    for w in s.split():
        u = w.upper().strip(".")
        if u in ACRONYMS:
            out.append(u)
        elif re.match(r"^[0-9]+[a-z]?$", w, re.I):
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower() if w else w)
    return " ".join(out)


def strip_common_prefix(bases):
    if len(bases) < 2:
        return bases
    splits = [b.split() for b in bases]
    n = min(len(s) for s in splits)
    common = 0
    for i in range(n):
        tok = splits[0][i].lower()
        if all(len(s) > i and s[i].lower() == tok for s in splits):
            common += 1
        else:
            break
    return [" ".join(s[common:] or s[-1:]) for s in splits]


def clean_doc_title(text):
    t = text.strip(" -–—")
    t = re.sub(r"^(contest\s+problem|contest)\s+", "", t, flags=re.I).strip(" -–—")
    t = re.sub(r"\s*\(\d[\d.]*\s*[kmg]b\)\s*$", "", t, flags=re.I).strip(" -–—")
    if not t:
        t = text.strip(" -–—") or "Problem"
    return titlecase(t) if (t.isupper() or t.islower()) else t


_DATEISH = re.compile(
    r"\b(19|20)\d{2}\b|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|^\d+\s*[-–]\s*\d+$",
    re.I)


def loc_hint(loc):
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    while parts and _DATEISH.search(parts[-1]):  # drop trailing date components
        parts.pop()
    if not parts:
        return ""
    return ", ".join(parts[-2:]) if len(parts) >= 2 else parts[-1]


def dedupe(titles):
    seen, out = {}, []
    for t in titles:
        t = t or "Document"
        if t in seen:
            seen[t] += 1
            out.append(f"{t} ({seen[t]})")
        else:
            seen[t] = 1
            out.append(t)
    return out


def folder_doc_titles(filenames):
    bases = [re.sub(r"\s+", " ", os.path.splitext(f)[0].replace("_", " ")).strip() for f in filenames]
    return dedupe([titlecase(t) or "Document" for t in strip_common_prefix(bases)])


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def safe_filename(year, anchor, group_slug, fname):
    stem, ext = os.path.splitext(fname)
    return f"{slugify(f'{year}_{anchor}_{group_slug}_{stem}')}{ext.lower()}"


# ----------------------------------------------------------------------------- plan


def plan_archive(year, suffix):
    index_orig = f"{SITE}{year}_{suffix}/"
    try:
        page = cached(wb(index_orig)).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        print(f"  !! index fetch failed {year}: {e!r}"[:120])
        return []
    out = []
    for anchor, section in split_sections(page):
        name, loc = contest_meta(section)
        if not name:
            continue
        if (str(year), anchor) in PROTECT:
            continue
        problems = []
        for label, links in section_groups(section, index_orig):
            if is_excluded(label):
                continue
            folders = [(t, u) for t, u, isf, ise in links if isf]
            directs = [(t, u) for t, u, isf, ise in links if not isf and not ise
                       and is_doc(u) and not is_image(u)]
            for ftext, forig in folders:
                try:
                    listing = cached(wb(forig)).decode("utf-8", "replace")
                except Exception as e:  # noqa: BLE001
                    print(f"    !! listing failed {forig}: {e!r}"[:120])
                    continue
                files = [(fn, hr, og) for fn, hr, og in parse_listing(listing, forig)
                         if is_doc(fn) and not is_image(fn)]
                if not files:
                    continue
                titles = folder_doc_titles([fn for fn, _, _ in files])
                gslug = slugify(forig.rstrip("/").rsplit("/", 1)[-1])
                problems.append({
                    "title": ftext or titlecase(gslug),
                    "slug": gslug,
                    "docs": [{"title": t, "fname": fn,
                              "raw": wb_raw(re.search(r"/web/(\d+)", hr).group(1), og)}
                             for (fn, hr, og), t in zip(files, titles)],
                })
            if directs:
                titles = dedupe([clean_doc_title(t) for t, _ in directs])
                gslug = slugify(label) or "problem"
                problems.append({
                    "title": label or "Contest Problem",
                    "slug": gslug,
                    "docs": [{"title": t,
                              "fname": urllib.parse.unquote(urllib.parse.urlsplit(u).path.rsplit("/", 1)[-1]),
                              "raw": wb_raw(TS, u)}
                             for (_, u), t in zip(directs, titles)],
                })
        if problems:
            out.append({"year": str(year), "anchor": anchor, "name": name,
                        "loc": loc, "problems": problems})
    # disambiguate distinct contests that derive the same name (e.g. two
    # "Rocky Mountain Mine Rescue Contest" in one year) so get_or_create by
    # name can't merge them.
    return out


def disambiguate(contests):
    """Qualify same-named contests within a year (incl. across coal + M/NM
    archives) so get_or_create by name can't merge two distinct contests."""
    counts = Counter(c["name"] for c in contests)
    for c in contests:
        if counts[c["name"]] > 1:
            c["name"] = f"{c['name']} ({loc_hint(c['loc']) or c['anchor']})"
    return contests


def archives_for(year):
    return ["Unified_Contests"] if year >= 2021 else ["Coal_Contests", "Contests"]


# ----------------------------------------------------------------------------- write


def magic_ok(data, ext):
    if ext == ".pdf":
        return data[:5] == b"%PDF-"
    if ext in (".docx", ".xlsx", ".pptx"):
        return data[:2] == b"PK"
    return len(data) > 8


def ingest_contest(c, do_write):
    year, anchor = c["year"], c["anchor"]
    comp_name = f"{year} {c['name']}"
    if (year, anchor) in PROTECT:
        print(f"  ~ PROTECTED, skipping: {comp_name}")
        return (0, 0, 0)
    n_prob = n_doc = n_skip = 0
    comp = None
    if do_write:
        comp, _ = Competition.objects.get_or_create(
            name=comp_name, defaults={"year": int(year), "description": c["loc"]})
    for pi, p in enumerate(c["problems"]):
        prob = None
        if do_write:
            prob, _ = CompetitionProblem.objects.get_or_create(
                competition=comp, title=p["title"], defaults={"sort_order": (pi + 1) * 10})
        n_prob += 1
        for di, d in enumerate(p["docs"]):
            target = safe_filename(year, anchor, p["slug"], d["fname"])
            rel = f"problems/{target}"
            abspath = os.path.join(MEDIA, rel)
            ext = os.path.splitext(target)[1].lower()
            if do_write and prob.documents.filter(file=rel).exists():
                n_skip += 1
                continue
            if do_write:
                if not os.path.exists(abspath):
                    time.sleep(DOWNLOAD_DELAY)
                    try:
                        data = fetch(d["raw"])
                    except Exception as e:  # noqa: BLE001
                        print(f"      !! download failed {d['fname']}: {e!r}"[:120])
                        continue
                    if not magic_ok(data, ext):
                        print(f"      !! bad bytes {d['fname']}: {data[:8]!r}")
                        continue
                    with open(abspath, "wb") as f:
                        f.write(data)
                    time.sleep(0.4)  # be polite to Wayback over hundreds of files
                ProblemDocument.objects.get_or_create(
                    problem=prob, file=rel,
                    defaults={"title": d["title"], "sort_order": (di + 1) * 10})
            n_doc += 1
    flag = "" if do_write else "  [DRY-RUN]"
    print(f"  + {comp_name}{flag}  ({len(c['problems'])} problems, {n_doc} docs"
          + (f", {n_skip} present" if n_skip else "") + ")")
    for p in c["problems"]:
        print(f"        - {p['title']} ({len(p['docs'])}): "
              + ", ".join(d["title"] for d in p["docs"][:7])
              + (" ..." if len(p["docs"]) > 7 else ""))
    return (n_prob, n_doc, n_skip)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--year", type=int)
    ap.add_argument("--years", type=int, nargs="+")
    args = ap.parse_args()
    years = args.years or ([args.year] if args.year else [2021, 2022, 2023, 2024])
    do_write = not args.dry_run
    tot = [0, 0, 0, 0]
    for year in years:
        print(f"\n================= {year} =================")
        contests = []
        for suffix in archives_for(year):
            contests += plan_archive(year, suffix)
        disambiguate(contests)
        print(f"  {len(contests)} contests with problem content\n")
        for c in contests:
            np, nd, ns = ingest_contest(c, do_write)
            tot[0] += 1; tot[1] += np; tot[2] += nd; tot[3] += ns
    print(f"\n===== {'WROTE' if do_write else 'PLANNED'}: {tot[0]} contests, "
          f"{tot[1]} problems, {tot[2]} docs"
          + (f", {tot[3]} already present" if tot[3] else "") + " =====")


if __name__ == "__main__":
    main()
