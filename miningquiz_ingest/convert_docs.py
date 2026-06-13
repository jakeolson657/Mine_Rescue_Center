"""Convert non-previewable problem documents (.docx/.doc/.rtf/.ppt/.pptx/.xlsx)
to PDF via the installed MS Office apps, so they preview in-browser.

Each Office app is launched ONCE and reused across all its files (far faster
than docx2pdf's open/close-per-file). Every output is byte-checked (%PDF-)
before the DB row is repointed and the source removed. Idempotent + resumable:
documents already previewable (pdf/txt/image) are skipped, so re-running only
picks up what's left.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from pages.models import ProblemDocument  # noqa: E402
import win32com.client as win32  # noqa: E402

MEDIA = settings.MEDIA_ROOT
WORD = {".docx", ".doc", ".rtf"}
PPT = {".ppt", ".pptx"}
XL = {".xlsx", ".xls"}


def unique_pdf(rel):
    """Avoid clobbering an existing same-stem .pdf belonging to another doc."""
    if not os.path.exists(os.path.join(MEDIA, rel)):
        return rel
    stem, ext = os.path.splitext(rel)
    i = 2
    while os.path.exists(os.path.join(MEDIA, f"{stem}_{i}{ext}")):
        i += 1
    return f"{stem}_{i}{ext}"


def collect():
    buckets = {"word": [], "ppt": [], "xl": []}
    for d in ProblemDocument.objects.all():
        if d.preview_kind != "":
            continue
        e = os.path.splitext(d.file.name)[1].lower()
        if e in WORD:
            buckets["word"].append(d)
        elif e in PPT:
            buckets["ppt"].append(d)
        elif e in XL:
            buckets["xl"].append(d)
    return buckets


def finalize(d, src_abs, dst_abs, dst_rel, fails):
    if os.path.exists(dst_abs) and open(dst_abs, "rb").read(5) == b"%PDF-":
        d.file = dst_rel
        d.save(update_fields=["file"])
        if os.path.abspath(src_abs) != os.path.abspath(dst_abs):
            try:
                os.remove(src_abs)
            except OSError:
                pass
        return True
    fails.append(d.file.name)
    return False


def run_bucket(name, docs, opener):
    ok, fails = 0, []
    print(f"[{name}] {len(docs)} files", flush=True)
    for i, d in enumerate(docs):
        src = os.path.abspath(os.path.join(MEDIA, d.file.name))
        dst_rel = unique_pdf(os.path.splitext(d.file.name)[0] + ".pdf")
        dst = os.path.abspath(os.path.join(MEDIA, dst_rel))
        try:
            opener(src, dst)
            finalize(d, src, dst, dst_rel, fails)
        except Exception as ex:  # noqa: BLE001
            fails.append(f"{os.path.basename(d.file.name)}: {ex!r}"[:110])
        if (i + 1) % 20 == 0:
            print(f"[{name}] {i + 1}/{len(docs)} done", flush=True)
    print(f"[{name}] converted {len(docs) - len(fails)}, failed {len(fails)}", flush=True)
    for f in fails:
        print(f"    FAIL {f}", flush=True)
    return ok, fails


def main():
    b = collect()
    print(f"to convert -> word:{len(b['word'])} ppt:{len(b['ppt'])} xl:{len(b['xl'])}", flush=True)

    if b["word"]:
        app = win32.Dispatch("Word.Application")
        app.Visible = False
        try:
            app.DisplayAlerts = 0
        except Exception:  # noqa: BLE001
            pass

        def w(src, dst):
            doc = app.Documents.Open(src, ReadOnly=True, AddToRecentFiles=False)
            doc.SaveAs(dst, FileFormat=17)  # wdFormatPDF
            doc.Close(False)

        run_bucket("word", b["word"], w)
        app.Quit()

    if b["ppt"]:
        app = win32.Dispatch("PowerPoint.Application")  # must stay visible

        def p(src, dst):
            pres = app.Presentations.Open(src, ReadOnly=True, WithWindow=False)
            pres.SaveAs(dst, 32)  # ppSaveAsPDF
            pres.Close()

        run_bucket("ppt", b["ppt"], p)
        app.Quit()

    if b["xl"]:
        app = win32.Dispatch("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False

        def x(src, dst):
            wb = app.Workbooks.Open(src, ReadOnly=True)
            wb.ExportAsFixedFormat(0, dst)  # xlTypePDF
            wb.Close(False)

        run_bucket("xl", b["xl"], x)
        app.Quit()

    remaining = sum(1 for d in ProblemDocument.objects.all() if d.preview_kind == "")
    print(f"\nDONE. documents still not previewable: {remaining}", flush=True)


if __name__ == "__main__":
    main()
