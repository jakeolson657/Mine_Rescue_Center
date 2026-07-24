import django, os, sys, json
SCR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCR)                     # sibling pipeline modules
sys.path.insert(0, os.path.dirname(SCR))    # repo root (config/, pages/)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import extractor
from django.conf import settings
from pages.models import ProblemDocument


def mk(stem, choices, correct_letter):
    idx = 'ABC'.index(correct_letter)
    return {'text': stem, 'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(choices)]}


BG4 = [
 mk("The drainage valve opens at approximately ___ and is therefore out of the RZ reading range.", ["20 mbars", "15 mbars", "25 mbars"], "B"),
 mk("Check the supply of oxygen gas on the display unit at intervals of approximately ___.", ["20 minutes", "15 minutes", "60 minutes"], "B"),
 mk("All parts which come in contact with exhaled air must be thoroughly cleaned and ___ after use.", ["dried", "rinsed", "disinfected"], "C"),
 mk("The breathing bag has a ___ volume.", ["5.5 liter", "5.2 liter", "5.8 liter"], "A"),
 mk("Relief valve activation is ___ (87psi).", ["6 bar", "10 mbar", "5 bar"], "A"),
 mk("At the last low pressure warning approximately ___ of the oxygen has been used up.", ["75 %", "90 %", "95 %"], "C"),
 mk("Only oxygen (medical grade or better) with greater than ___ purity is to be used to fill the BG-4 oxygen cylinders.", ["95.9 %", "97.5 %", "99.5 %"], "C"),
 mk("The first low pressure warning occurs when the pressure drops to approximately ___.", ["750 psi", "700 psi", "145 psi"], "B"),
 mk("During the positive pressure leak test, the pressure change within 1 minute must be lower than ___.", ["1 mbar", "10 mbar", ".1 mbar"], "A"),
 mk("A positive pressure in the breathing circuit prevents ___ air from entering the system.", ["contaminated", "mine", "ambient"], "C"),
 mk("The oxygen cylinder safety burst disc ruptures at ___ (275 bar).", ["3,750 psi", "4,000 psi", "3,200 psi"], "B"),
 mk("Medium pressure in the BG-4 is between ___ psi and 64 psi.", ["58", "52", "56"], "A"),
 mk("The maximum temperature of the air used to dry parts should not go above 60 degrees C (___ F).", ["120 degrees", "160 degrees", "140 degrees"], "C"),
 mk("It is safe to use the BG-4 for up to ___ with a battery warning 1 icon.", ["8 hours", "4 hours", "6 hours"], "B"),
 mk("Rubber parts must be particularly protected from direct exposure to ___.", ["heat", "radiation", "chemicals"], "B"),
 mk("U.S. D.O.T. hydro test composite cylinders every ___ years.", ["5", "6", "3"], "A"),
 mk("The pressure reducer must be rebuilt / overhauled every ___.", ["5 years", "3 years", "6 years"], "C"),
 mk("First stage reducer bypass output is greater than ___ / min.", ["80 L", "60 L", "50 L"], "C"),
 mk("The minimum valve provides greater than ___ / min flow.", ["80 L", "50 L", "60 L"], "A"),
 mk("The BG-4 constant dosage must be 1.5 to ___ / min.", ["1.7 L", "1.9 L", "1.8 L"], "B"),
]

BIO = [
 mk("Constant use is defined as being in use at least ___.", ["once a week", "once a month", "every 2 weeks"], "B"),
 mk("The CO2 Scrubber should be replaced after ___.", ["4 hours", "removing lid", "1 use"], "C"),
 mk("The Bio Pak 240 Revolution is approved when the oxygen cylinder is fully charged with compressed ___ grade oxygen at 3000psi.", ["hospital, pure", "medical, aviation", "hospital, divers"], "B"),
 mk("A low battery alarm is indicated by a Red, Green, Blue light sequence followed by a short alarm chirp any time the battery will not complete a ___ mission.", ["four-hour", "mine rescue", "underground recovery"], "A"),
 mk("Allow all components to remain wetted by the cleaning solution a minimum of ___.", ["15 minutes", "5 minutes", "10 minutes"], "C"),
 mk("Bio Pak tidal volume is over ___.", ["6 liters", "5 liters", "6.5 liters"], "A"),
 mk("Allow the oxygen cylinder to ___ after filling to determine the correct pressure.", ["stabilize", "settle", "cool"], "C"),
 mk("The Bio Pak 240 Revolution is suitable for respiratory protection during entry into and escape from oxygen deficient atmospheres with a temperature range of ___ F (-15C) to 110 degree F (43C).", ["15 degree F", "5 degree F", "10 degree F"], "B"),
 mk("The RMS Module IS NOT ___ with the TRIM light pipe connector or the battery door removed.", ["watertight", "sealed", "air tight"], "A"),
 mk("DOT require carbon fiber wrapped aluminum cylinders be tested by an approved facility on a 5-year cycle from the date ___.", ["in service", "of purchase", "of manufacture"], "C"),
 mk("Freeze the ice canister for a minimum of 8 hours before use at a maximum temperature of ___ (-12C).", ["10 degrees F", "5 degrees F", "15 degrees F"], "A"),
 mk("In addition to normal Turn-Around Maintenance, the SCBA shall be ___ and high-pressure tested on a monthly basis if the SCBA is in constant use once a month or placed into long-term storage.", ["properly assembled", "visually inspected", "thoroughly cleaned"], "B"),
 mk("Do not expose opened CO2 scrubber cartridges to ambient air for more than ___.", ["30 minutes", "15 minutes", "20 minutes"], "C"),
 mk("If the cylinder is removed for washing you must attach the Regulator Wash Cover provided in the test kit to seal off the regulator from ___ while washing the lower housing.", ["water", "dirt", "contamination"], "C"),
 mk("A good facepiece seal is important to achieving ___ and proper SCBA duration.", ["full protection", "sufficient oxygen", "reduced leakage"], "A"),
 mk("The hoses and facepiece adapter MUST be installed with the breathing gas directional arrows facing ___.", ["DOWN", "UP", "SIDEWAYS"], "B"),
 mk("Do not change battery in ___.", ["hazardous area", "explosive atmospheres", "contaminated atmospheres"], "A"),
 mk("To get the most accurate flow meter reading you must have a minimum of ___ (104 bar) in the cylinder.", ["2000 psi", "1500 psi", "1750 psi"], "B"),
 mk("The RMS will automatically power down once the system pressure has dropped below ___.", ["50 psi", "150 psi", "25 psi"], "C"),
 mk("The low oxygen alarm must activate between ___ psig and is indicated by a flashing red light and audible alarm.", ["650-750", "650-700", "600-650"], "A"),
]

BIOM_KEY = {1: 'B', 2: 'C', 3: 'B', 4: 'A', 5: 'B', 6: 'A', 7: 'C', 8: 'B', 9: 'A', 10: 'A',
            11: 'B', 12: 'B', 13: 'A', 14: 'A', 15: 'B', 16: 'C', 17: 'A', 18: 'C', 19: 'A'}
path = os.path.join(settings.MEDIA_ROOT, ProblemDocument.objects.get(pk=1791).file.name)
raw = extractor.extract_questions(path, max_pages=4)[0]
BIOM = []
for q in raw:
    n = q['number']
    if n not in BIOM_KEY:
        continue
    ch = [extractor.clean_text(c['raw']) for c in q['choices'] if extractor.clean_text(c['raw']).strip()]
    idx = 'ABCDE'.index(BIOM_KEY[n])
    if len(ch) < 2 or idx >= len(ch):
        continue
    BIOM.append({'text': extractor.clean_text(q['text']),
                 'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(ch)]})
# q20 isn't in the p6 key (it stops at 19); added from the test page, answer A
# (temperature range -15C = 5 F). Choice C bleeds the next page's header via the
# extractor, so this one is spelled out cleanly.
BIOM.append(mk("The BioPak 240 Revolution is suitable for respiratory protection during entry into and escape from oxygen deficient atmospheres with a temperature range of ___ degree F (-15C) to 110 degree F (43C).", ["5", "10", "15"], "A"))

# ---- Kentucky Post 2 BG4 (pk1792): text layer, key read by eye from p13 ----
# q1-20 are multiple choice; 21-30 are diagram-based parts (skipped). The header
# page (p0) carries a stray parts answer list that parses as choice-less "Q20-30";
# filtering to choices>=2 and number<=20 keeps only the real MC questions.
KENT_KEY = {1: 'C', 2: 'C', 3: 'B', 4: 'B', 5: 'B', 6: 'C', 7: 'A', 8: 'C', 9: 'A', 10: 'A',
            11: 'A', 12: 'B', 13: 'B', 14: 'A', 15: 'A', 16: 'B', 17: 'B', 18: 'C', 19: 'C', 20: 'C'}
path2 = os.path.join(settings.MEDIA_ROOT, ProblemDocument.objects.get(pk=1792).file.name)
raw2 = extractor.extract_questions(path2, max_pages=4)[0]
KENT, seen = [], set()
for q in raw2:
    n = q['number']
    if n not in KENT_KEY or n in seen:
        continue
    ch = [extractor.clean_text(c['raw']) for c in q['choices'] if extractor.clean_text(c['raw']).strip()]
    idx = 'ABCDE'.index(KENT_KEY[n])
    if len(ch) < 2 or idx >= len(ch):
        continue
    seen.add(n)
    KENT.append({'text': extractor.clean_text(q['text']),
                 'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(ch)]})

# ---- 2014 Alabama Day 1 (pk1795): clean questions (answers redacted from the
# "Day 1 Written Test Answers" PDF); key read by eye from that answered PDF's red
# "(C)" markers. The red marker breaks the extractor's choice-splitter on the
# answered doc, so questions come from the redacted clean doc + this letter key.
DAY1_KEY = {1: 'C', 2: 'B', 3: 'B', 4: 'A', 5: 'B', 6: 'C', 7: 'C', 8: 'C', 9: 'A', 10: 'C'}
path3 = os.path.join(settings.MEDIA_ROOT, ProblemDocument.objects.get(pk=1795).file.name)
raw3 = extractor.extract_questions(path3)[0]
DAY1 = []
for q in raw3:
    n = q['number']
    if n not in DAY1_KEY:
        continue
    ch = [extractor.clean_text(c['raw']) for c in q['choices'] if extractor.clean_text(c['raw']).strip()]
    idx = 'ABC'.index(DAY1_KEY[n])
    if len(ch) < 2 or idx >= len(ch):
        continue
    DAY1.append({'text': extractor.clean_text(q['text']),
                 'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(ch)]})

# ---- 2014 Southwest Regional First Aid (test pk1115, answers doc pk1116) ----
# pk1116 repeats the test with the answer as a "C page 291" line after each
# question. Key is those letters in order; questions come from pk1116 (cleaner),
# with the trailing "<letter> pg. N" / "pg N" citation choices stripped/dropped.
import re as _re2
FA_KEY = ['C', 'C', 'A', 'C', 'B', 'D', 'B', 'D', 'A', 'C', 'D', 'B', 'B', 'A', 'C',
          'A', 'D', 'D', 'D', 'B', 'A', 'D', 'C', 'C', 'D']


def _fa_clean_choices(raw):
    out = []
    for c in raw:
        t = _re2.sub(r'\s*[A-Da-d]?\s*(?:pg|page)\.?\s*[\d\.\s]*$', '', c, flags=_re2.I).strip()
        t = extractor.clean_text(t)
        if t and not _re2.match(r'^(?:pg|page)\b', t, _re2.I):
            out.append(t)
    return out


fa_path = os.path.join(settings.MEDIA_ROOT, ProblemDocument.objects.get(pk=1116).file.name)
fa_raw = extractor.extract_questions(fa_path)[0]
FA = []
for q in fa_raw:
    n = q['number']
    if not (1 <= n <= len(FA_KEY)):
        continue
    ch = _fa_clean_choices([c['raw'] for c in q['choices']])
    idx = 'ABCD'.index(FA_KEY[n - 1])
    if len(ch) < 2 or idx >= len(ch):
        continue
    FA.append({'text': extractor.clean_text(q['text']),
               'choices': [{'text': c, 'is_correct': j == idx} for j, c in enumerate(ch)]})

# ---- 2016 NMRA Post 6 Preshift (pk1281): yellow-highlighted answers only on the
# first two pages; pages 3-4 are an unanswered copy of the test, so bound the
# extractor to p0-1 (the answered section).
r1281 = extractor.extract(ProblemDocument.objects.get(pk=1281).file.name, None, max_pages=2)
PRESHIFT1281 = r1281['questions'] if r1281.get('clean') else []

from scanned_quizzes import SCANNED, BG4_PARTS, BIOPAK_PARTS, KENT_PARTS  # scanned + parts
from text_quizzes import TEXT_QUIZZES  # programmatic text-layer quizzes

out = list(SCANNED) + list(TEXT_QUIZZES) + [
 {'source_pk': 1281, 'title': 'Preshift Written Test', 'questions': PRESHIFT1281},
 {'source_pk': 1115, 'title': 'First Aid Written Test', 'questions': FA},
 {'source_pk': 1795, 'title': 'Day 1 Written Test', 'questions': DAY1},
 {'source_pk': 1791, 'title': 'BioMarine 240R Bench Written Test', 'questions': BIOM},
 {'source_pk': 1792, 'title': 'Kentucky Post 2 Bench Written Test', 'questions': KENT + KENT_PARTS},
 {'source_pk': 1793, 'title': 'BG-4 Bench Written Test', 'questions': BG4 + BG4_PARTS},
 {'source_pk': 1794, 'title': 'BioPak 240-R Bench Written Test', 'questions': BIO + BIOPAK_PARTS},
]
json.dump(out, open(os.path.join(SCR, 'manual_quizzes.json'), 'w', encoding='utf-8'), indent=1)
for o in out:
    ok = all(sum(c['is_correct'] for c in q['choices']) == 1 for q in o['questions'])
    print(f"{o['title']}: {len(o['questions'])} q  all-single-correct={ok}")
