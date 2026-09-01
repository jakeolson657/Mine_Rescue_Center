"""Build the interactive quiz for the 2026 Fallen Heroes pre-shift written test.

The test is a 10-question, three-choice paper. Question and choice text come from
the TEST pdf (the paper the contestants actually took, and the document the quiz
hangs off), while the correct answers come from the separate answer-KEY pdf,
which marks the right choice by colouring its text red (ee0000):

  - test -> ProblemDocument 2053   (2026 Fallen Heroes Pre-Shift Written Test.pdf)
  - key  -> ProblemDocument 2054   (... Written Test Key.pdf)

Both PDFs were split out of the organiser's 18-page pre-shift PowerPoint deck --
see local_2026_ingest/ingest_fallen_heroes.py.

Parsing: lines are read with PyMuPDF; a line beginning "N." opens a question and
lines beginning "a"/"b"/"c" (period optional -- the key writes "a 150") are its
choices, everything else continues the current stem. Headers are skipped by exact
text. In the key, a choice is correct when it carries red text containing at
least one ALPHANUMERIC character: the key has a stray red period inside question
2's choice b, and a naive "any red span" test would mark it as a second answer.
The two files are cross-checked question-by-question and letter-by-letter before
the answers are transferred, so a future re-split that shifts pages fails loudly
instead of mis-keying the quiz.

Writes fallen_heroes_2026_preshift.json in the insert_one_quiz.py schema;
--load then inserts it via insert_one_quiz.

Run:  PYTHONUTF8=1 venv/Scripts/python.exe quiz_pipeline/build_fallen_heroes_2026_quiz.py [--load]
"""
import argparse
import json
import os
import re
import subprocess
import sys

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))

SRC_DIR = (r"C:\Users\Jacob\OneDrive - Colorado School of Mines\Documents"
           r"\Mine Rescue Center\Past Problems\2026\Fallen Heroes")
TEST_PDF = "2026 Fallen Heroes Pre-Shift Written Test.pdf"
KEY_PDF = "2026 Fallen Heroes Pre-Shift Written Test Key.pdf"

SOURCE_PK = 2053          # the test document -- where the "Take Test" button goes
TITLE = "Pre-Shift Written Test"
OUT = "fallen_heroes_2026_preshift.json"
EXPECT_Q = 10
EXPECT_CHOICES = 3

RED = {0xEE0000, 0xFF0000}
SKIP_LINES = {
    "WRITTEN EXAM  (PRE-SHIFT CONTEST)",
    "ANSWER KEY",
}
SKIP_PREFIXES = ("Team Name", "Contestant Number")

QNUM_RE = re.compile(r"^\s*(\d{1,2})\s*[.)]\s*")
# The key drops the period on one choice ("a 150"), so the separator is optional
# -- but it must be followed by whitespace, or stems like "any source of electric
# current." would parse as choice "a".
CHOICE_RE = re.compile(r"^\s*([abc])\s*(?:[.)]\s*|\s+)(?=\S)")

# Stray punctuation the organiser's deck carries mid-sentence. Corrected in the
# interactive quiz only; the archived test/key PDFs keep the original wording
# (see the site's preserve-the-organiser's-document policy). Neither touches a
# choice, so no answer changes. Asserted below so a stale fix can't silently
# no-op if the source is ever re-split.
TEXT_FIXES = [
    ("soldering .with", "soldering with"),   # q2 stem: stray period
]


def lines_with_red(path):
    """[(text, red_alnum_count)] for every non-empty line, in reading order."""
    out = []
    for page in fitz.open(path):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"])
                if not text.strip():
                    continue
                red = sum(
                    sum(ch.isalnum() for ch in s["text"])
                    for s in line["spans"] if s["color"] in RED
                )
                out.append((text, red))
    return out


def parse(path):
    """{question number: {'stem': str, 'choices': {letter: (text, red)}}}."""
    questions, num, letter = {}, None, None
    for text, red in lines_with_red(path):
        stripped = text.strip()
        if stripped in SKIP_LINES or stripped.startswith(SKIP_PREFIXES):
            continue
        m = QNUM_RE.match(text)
        if m:
            num, letter = int(m.group(1)), None
            questions[num] = {"stem": text[m.end():], "choices": {}}
            continue
        if num is None:
            continue
        m = CHOICE_RE.match(text)
        if m:
            letter = m.group(1)
            questions[num]["choices"][letter] = [text[m.end():], red]
            continue
        # Continuation of whichever part of the question we are inside.
        if letter:
            questions[num]["choices"][letter][0] += " " + stripped
            questions[num]["choices"][letter][1] += red
        else:
            questions[num]["stem"] += " " + stripped
    return questions


def clean(text):
    """Tidy the deck's spacing without changing any wording: collapse runs of
    whitespace, drop doubled sentence periods, close the gap before punctuation
    and open one after it ("Welding,cutting" -> "Welding, cutting")."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.])", r"\1", text)
    text = re.sub(r"([,.])(?=[A-Za-z])", r"\1 ", text)
    text = re.sub(r"\.{2,}", ".", text)
    return text.strip().lstrip(". ").strip()


def clean_choice(text):
    """As clean(), plus the trailing full stop one choice carries and the others
    don't ("c. miners." against "b. escapeways") -- kept off the stems, which are
    real sentences. Interior periods ("12.1") are untouched."""
    return re.sub(r"\.$", "", clean(text))


def build():
    test = parse(os.path.join(SRC_DIR, TEST_PDF))
    key = parse(os.path.join(SRC_DIR, KEY_PDF))

    assert sorted(test) == sorted(key) == list(range(1, EXPECT_Q + 1)), \
        f"question numbers differ: test={sorted(test)} key={sorted(key)}"

    questions = []
    positions = []
    for num in range(1, EXPECT_Q + 1):
        t, k = test[num], key[num]
        letters = sorted(t["choices"])
        assert letters == sorted(k["choices"]) == list("abc"[:EXPECT_CHOICES]), \
            f"q{num}: choice letters differ (test={letters}, key={sorted(k['choices'])})"
        # Same paper, so the choices must still say the same thing -- the two
        # copies differ only in capitalisation and spacing.
        for letter in letters:
            a = re.sub(r"[^a-z0-9]", "", t["choices"][letter][0].lower())
            b = re.sub(r"[^a-z0-9]", "", k["choices"][letter][0].lower())
            assert a == b, f"q{num}{letter}: test {a!r} != key {b!r}"

        correct = [l for l in letters if k["choices"][l][1] > 0]
        assert len(correct) == 1, f"q{num}: {len(correct)} red choices, expected 1"
        positions.append(correct[0])

        stem = clean(t["stem"])
        for wrong, right in TEXT_FIXES:
            if wrong in t["stem"]:
                stem = clean(t["stem"].replace(wrong, right))
        questions.append({
            "text": stem,
            "choices": [
                {"text": clean_choice(t["choices"][l][0]), "is_correct": l == correct[0]}
                for l in letters
            ],
        })

    applied = sum(w in " ".join(q["stem"] for q in test.values()) for w, _ in TEXT_FIXES)
    assert applied == len(TEXT_FIXES), "a TEXT_FIXES entry no longer matches the source"

    # Guardrails: no empty or duplicated choice text, and no answer-position skew
    # that would betray a broken detector.
    for i, q in enumerate(questions, 1):
        texts = [c["text"] for c in q["choices"]]
        assert all(texts) and len(set(texts)) == len(texts), f"q{i}: empty/duplicate choices"
    top = max(positions.count(l) for l in set(positions))
    assert top / len(positions) <= 0.85, f"answer positions skewed: {positions}"

    out = {"source_pk": SOURCE_PK, "title": TITLE, "questions": questions}
    path = os.path.join(HERE, OUT)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {path}: {len(questions)} questions, answers {''.join(positions)}")
    for i, q in enumerate(questions, 1):
        ans = next(c["text"] for c in q["choices"] if c["is_correct"])
        print(f"  {i:2d}. {q['text'][:78]}")
        print(f"      -> {ans}")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", action="store_true",
                    help="insert the quiz with insert_one_quiz.py after building")
    args = ap.parse_args()
    path = build()
    if args.load:
        subprocess.check_call([sys.executable, os.path.join(HERE, "insert_one_quiz.py"), path])
