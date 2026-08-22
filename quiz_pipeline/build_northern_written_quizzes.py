"""Build interactive quizzes for the 2026 Northern Mine Rescue Association
written tests from their answer-KEY docx files.

Each key docx marks the correct choice by coloring its text red (FF0000). The two
tests are simple multiple-choice / True-False papers:

  - Day 1 (30 q) key: "...day 2 MIne Rescue Test Key.docx" -> ProblemDocument 2034
  - Day 2 (30 q) key: "...Day 1 MIne Rescue Test Key.docx" -> ProblemDocument 2035

(The docx filenames disagree with their printed "Day N" headers; the printed
header is authoritative -- see ingest_northern_written.py.)

Parsing: skip the 3-line header, split the body on blank paragraphs into question
groups. In each group the trailing lines are the answer choices (2 when they are
True/False, otherwise 4); the remaining leading lines are the question stem. A
choice is correct when any run in its paragraph is red. The trailing manual
citation "(4-11)" on each stem is a page pointer, not part of the question, so it
is stripped; smart punctuation is normalised to ASCII.

Writes one JSON per test into quiz_pipeline/ (northern_2026_day{1,2}.json) in the
insert_one_quiz.py schema, then --load inserts them via insert_one_quiz.

Run:  PYTHONUTF8=1 venv/Scripts/python.exe quiz_pipeline/build_northern_written_quizzes.py [--load]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SRC_DIR = (r"C:\Users\Jacob\OneDrive - Colorado School of Mines\Documents"
           r"\Mine Rescue Center\Past Problems\2026"
           r"\Northern Mine Rescue Association Competition\Written Tests")

TESTS = [
    {
        "key": "2026 Northern Reginal day 2 MIne Rescue Test Key.docx",
        "source_pk": 2034,
        "title": "Day 1 Written Test",
        "expect": 30,
        "out": "northern_2026_day1.json",
    },
    {
        "key": "2026 Northern Reginal Day 1 MIne Rescue Test Key.docx",
        "source_pk": 2035,
        "title": "Day 2 Written Test",
        "expect": 30,
        "out": "northern_2026_day2.json",
    },
]


# Verified misspellings in the source docx, corrected in the interactive quiz
# (the archived test/key PDFs keep the contest's original wording). Each was
# confirmed to appear verbatim in the key docx and NONE is a correct answer --
# three are distractors, "Histeria" is in a stem -- so no answer changes.
# Deliberately NOT "corrected": mining/technical terms a spell-checker flags but
# which are right (escapeway, inby, Pitot, Monoammonium, MSHA, M/NM), and
# "gasses", an accepted variant plural of gas.
SPELLING_FIXES = [
    ("Eyesite", "Eyesight"),          # Day 1 q10 distractor
    ("Hight, Width", "Height, Width"),  # Day 1 q15 distractor
    ("Histeria", "Hysteria"),         # Day 2 q28 stem
    ("Restraining Devise", "Restraining Device"),  # Day 2 q29 distractor
]


def apply_spelling_fixes(questions):
    """Apply SPELLING_FIXES across stems and choices; return a hit count per fix
    so the caller can assert every fix still matches the source."""
    hits = {old: 0 for old, _ in SPELLING_FIXES}
    for q in questions:
        for old, new in SPELLING_FIXES:
            if old in q["text"]:
                q["text"] = q["text"].replace(old, new)
                hits[old] += 1
            for c in q["choices"]:
                if old in c["text"]:
                    c["text"] = c["text"].replace(old, new)
                    hits[old] += 1
    return hits


def norm(text):
    """ASCII-normalise smart punctuation and collapse whitespace."""
    repl = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " "}
    for a, b in repl.items():
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def clean_stem(text):
    """Drop the trailing manual page citation, e.g. '(4-11)' or an unclosed
    '(5-7'. It is a study pointer, not part of the question."""
    text = re.sub(r"\s*\(\s*\d+\s*-\s*\d+\s*\)?\s*$", "", text)
    return text.strip()


def read_paragraphs(path):
    """[(text, is_red)] for each non-empty-or-separating paragraph. A paragraph
    is red if any of its runs has color FF0000."""
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    out = []
    for p in root.iter(NS + "p"):
        red = False
        parts = []
        for r in p.iter(NS + "r"):
            rpr = r.find(NS + "rPr")
            if rpr is not None:
                c = rpr.find(NS + "color")
                if c is not None and (c.get(NS + "val", "").upper() == "FF0000"):
                    red = True
            parts.append("".join(n.text or "" for n in r.iter(NS + "t")))
        out.append((norm("".join(parts)), red))
    return out


def build_questions(paras):
    # Drop the header: everything up to and including the "Team ... Position" line.
    start = 0
    for i, (t, _) in enumerate(paras):
        if re.search(r"\bTeam\b", t, re.I) and re.search(r"Position", t, re.I):
            start = i + 1
            break
    body = paras[start:]

    # Split into groups on blank lines.
    groups, cur = [], []
    for t, red in body:
        if t:
            cur.append((t, red))
        elif cur:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    questions = []
    for g in groups:
        texts = [t for t, _ in g]
        # True/False when the last two lines are exactly True / False.
        if len(g) >= 3 and texts[-2].lower() == "true" and texts[-1].lower() == "false":
            nchoice = 2
        else:
            nchoice = 4
        assert len(g) > nchoice, f"group too short for {nchoice} choices: {texts}"
        stem_lines = g[:-nchoice]
        choice_lines = g[-nchoice:]
        stem = clean_stem(norm(" ".join(t for t, _ in stem_lines)))
        choices = [{"text": t, "is_correct": red} for t, red in choice_lines]
        ncorrect = sum(c["is_correct"] for c in choices)
        assert ncorrect == 1, f"{ncorrect} correct in: {stem!r} -> {choice_lines}"
        questions.append({"text": stem, "choices": choices})
    return questions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", action="store_true",
                    help="insert each quiz via insert_one_quiz.py after building")
    args = ap.parse_args()

    total_hits = {old: 0 for old, _ in SPELLING_FIXES}
    for t in TESTS:
        paras = read_paragraphs(os.path.join(SRC_DIR, t["key"]))
        questions = build_questions(paras)
        assert len(questions) == t["expect"], \
            f"{t['title']}: parsed {len(questions)} questions, expected {t['expect']}"
        for old, n in apply_spelling_fixes(questions).items():
            total_hits[old] += n
        payload = {"source_pk": t["source_pk"], "title": t["title"],
                   "questions": questions}
        out_path = os.path.join(HERE, t["out"])
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        print(f"{t['title']}: {len(questions)} questions -> {t['out']}")
        if args.load:
            subprocess.run([sys.executable,
                            os.path.join(HERE, "insert_one_quiz.py"), out_path],
                           check=True)

    # Every correction must still match something, else the source changed and
    # the fix list is stale (silently correcting nothing would go unnoticed).
    unmatched = [old for old, n in total_hits.items() if n != 1]
    assert not unmatched, f"spelling fixes matched != 1 time: {unmatched} ({total_hits})"
    print("spelling fixes applied:", ", ".join(f"{o}->{n}" for o, n in SPELLING_FIXES))


if __name__ == "__main__":
    main()
