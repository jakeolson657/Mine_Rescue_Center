"""Render the diagram region of each parts page to media/quiz_images/ so the
manual parts-ID questions can show their exploded-view diagram. The diagram sits
in the top ~55% of the page; the answer-choice box below it is cropped off."""
import django, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import fitz
from django.conf import settings
from pages.models import ProblemDocument

IMG_DIR = os.path.join(settings.MEDIA_ROOT, 'quiz_images')
os.makedirs(IMG_DIR, exist_ok=True)

# (source_pk, [(page_index, image_basename, top_frac, bottom_frac), ...])
SPECS = [
    (913, [(2, '2014_ohiovalley_bench_lower_housing', 0.10, 0.64),
           (3, '2014_ohiovalley_bench_pneumatic', 0.08, 0.62),
           (4, '2014_ohiovalley_bench_center_section', 0.08, 0.62),
           (5, '2014_ohiovalley_bench_facemask', 0.08, 0.48)]),
    (1793, [(3, '2013_bg4_overview', 0.08, 0.68),
            (4, '2013_bg4_hose', 0.08, 0.72),
            (5, '2013_bg4_sentinel', 0.08, 0.75),
            (6, '2013_bg4_cylinder', 0.06, 0.78)]),
    (1794, [(3, '2013_biopak_complete', 0.08, 0.80),
            (4, '2013_biopak_lower_housing', 0.06, 0.66),
            (5, '2013_biopak_pneumatic', 0.06, 0.66),
            (6, '2013_biopak_manifold', 0.06, 0.66),
            (7, '2013_biopak_center_section', 0.06, 0.62),
            (8, '2013_biopak_facepiece', 0.06, 0.62),
            (9, '2013_biopak_lid', 0.06, 0.62),
            (10, '2013_biopak_diaphragm', 0.06, 0.62),
            (11, '2013_biopak_toolkit', 0.06, 0.62),
            (12, '2013_biopak_ice_canister', 0.06, 0.62)]),
    (1792, [(4, '2013_kentucky_cooling_canister', 0.11, 0.58),
            (5, '2013_kentucky_refillable_cartridge', 0.09, 0.56),
            (6, '2013_kentucky_drain_valve', 0.09, 0.55)]),
    (372, [(1, '2023_missouri_drager_sentinel', 0.08, 0.58),
           (2, '2023_missouri_drager_cylinder', 0.08, 0.66)]),
    (68, [(2, '2024_colorado_bio_pneumatic', 0.04, 0.56),
          (3, '2024_colorado_bio_lower_housing', 0.04, 0.56)]),
    (385, [(3, '2024_nevada_bg4_fps7000_mask', 0.04, 0.55),
           (4, '2024_nevada_bg4_breathing_house', 0.03, 0.53)]),
]
for pk, pages in SPECS:
    d = ProblemDocument.objects.get(pk=pk)
    doc = fitz.open(os.path.join(settings.MEDIA_ROOT, d.file.name))
    for pi, name, t, b in pages:
        page = doc[pi]
        r = page.rect
        clip = fitz.Rect(r.x0, r.y0 + r.height * t, r.x1, r.y0 + r.height * b)
        page.get_pixmap(clip=clip, dpi=150).save(os.path.join(IMG_DIR, name + '.png'))
        print('rendered', name)
