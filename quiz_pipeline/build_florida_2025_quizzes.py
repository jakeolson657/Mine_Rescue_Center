"""Build interactive quizzes for the 2025 Florida Surface contest's three written
tests, from the organizers' source .docx files.

All three papers share one clean structure in the docx: a question is a paragraph
numbered at ``ilvl 0`` of ``numId 1``; every other numbered paragraph is one of
its answer choices. Non-numbered paragraphs are cover/section headers and are
ignored. Each test is 30 four-choice questions.

Two different answer-key formats are handled:

  - **First Aid** — the key is a copy of the test with the correct choice
    highlighted yellow, so questions and answers come from the one file. Its
    stems also carry a study tag ("[Chapter 3q1]") that is stripped.
  - **Regional Field / Team Trainer** — the key is a separate one-page list of 30
    letters (plus a Brady page number or CFR cite). Questions come from the test
    docx and answer N is the Nth letter, so the count must match exactly.

Guardrails (see the project's quiz conventions): a question is kept only when it
resolves to exactly one correct choice out of four, the letter keys must line up
1:1 with the questions, and the answer-position spread is reported so a spurious
detector (everything in slot A) is visible before loading.

Writes one JSON per test into quiz_pipeline/ in the insert_one_quiz.py schema;
``--load`` then inserts each via insert_one_quiz.py.

Run:  PYTHONUTF8=1 venv/Scripts/python.exe quiz_pipeline/build_florida_2025_quizzes.py [--load]
"""
import argparse
import collections
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
           r"\7th Annual Surface Mining Emergency Response Training Competition")

TESTS = [
    {
        "questions": "2025 FLORIDA SURFACE CONTEST REGIONAL FIELD TEST.docx",
        "key": "Answer Key -2025 FLORIDA SURFACE CONTEST REGIONAL BRADY TEST.docx",
        "key_kind": "letters",
        "source_pk": 2042,          # Regional Field Competition Test
        "title": "Regional Field Competition Test",
        "expect": 30,
        "out": "florida_2025_field.json",
    },
    {
        "questions": "2025 FLORIDA SURFACE CONTEST FIRST AID TEST Actual with answers.docx",
        "key": None,                # answers are highlighted in the same file
        "key_kind": "highlight",
        "source_pk": 2044,          # First Aid Written Test
        "title": "First Aid Written Test",
        "expect": 30,
        "out": "florida_2025_first_aid.json",
    },
    {
        "questions": "2025 Florida Mine Rescue Team Trainer Test.docx",
        "key": "Answer Key - 2025 FLORIDA SURFACE TEAM TRAINER TEST.docx",
        "key_kind": "letters",
        "source_pk": 2046,          # Team Trainer Test
        "title": "Team Trainer Test",
        "expect": 30,
        "out": "florida_2025_team_trainer.json",
    },
]

# Study pointer the First Aid key prints ahead of each stem, e.g. "[Chapter 3q1]"
# or "[ Chapter 3q2]". Not part of the question.
CHAPTER_TAG_RE = re.compile(r"^\[\s*chapter[^\]]*\]\s*", re.I)


def norm(text):
    """ASCII-normalise smart punctuation and collapse whitespace."""
    repl = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " "}
    for a, b in repl.items():
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def paragraphs(path):
    """[(numId, ilvl, text, highlighted)] for every paragraph with text."""
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    out = []
    for p in root.iter(NS + "p"):
        num_id = ilvl = None
        ppr = p.find(NS + "pPr")
        if ppr is not None:
            npr = ppr.find(NS + "numPr")
            if npr is not None:
                n, i = npr.find(NS + "numId"), npr.find(NS + "ilvl")
                num_id = n.get(NS + "val") if n is not None else None
                ilvl = i.get(NS + "val") if i is not None else None
        highlighted = False
        parts = []
        for r in p.iter(NS + "r"):
            rpr = r.find(NS + "rPr")
            if rpr is not None:
                h = rpr.find(NS + "highlight")
                if h is not None and h.get(NS + "val", "").lower() not in ("", "none"):
                    highlighted = True
            parts.append("".join(t.text or "" for t in r.iter(NS + "t")))
        text = norm("".join(parts))
        if text:
            out.append((num_id, ilvl, text, highlighted))
    return out


def parse_questions(path):
    """Split a test docx into [{text, choices:[{text, is_correct}]}].

    A paragraph numbered ilvl 0 of numId 1 starts a question; any other numbered
    paragraph is a choice of the question in progress. ``is_correct`` is set here
    only for the highlight-marked keys; letter keys are applied by the caller."""
    questions = []
    for num_id, ilvl, text, hl in paragraphs(path):
        if num_id is None:
            continue                                  # cover / section header
        if num_id == "1" and ilvl in (None, "0"):
            questions.append({"text": CHAPTER_TAG_RE.sub("", text), "choices": []})
        elif questions:
            questions[-1]["choices"].append({"text": text, "is_correct": hl})
    return questions


def parse_letter_key(path):
    """The 30 answer letters from a one-page key: each row is a bare letter
    followed by a Brady page number or a CFR cite, so take the leading letter of
    every row that starts with a lone A-D. The page number sometimes runs
    straight into the letter ("D208"), so only a following LETTER disqualifies a
    row (which is what keeps the "Answer Key" heading out)."""
    letters = []
    for _, _, text, _ in paragraphs(path):
        m = re.match(r"^([A-D])(?![A-Za-z])", text.strip(), re.I)
        if m:
            letters.append(m.group(1).upper())
    return letters


def build(test, verbose=True):
    qpath = os.path.join(SRC_DIR, test["questions"])
    questions = parse_questions(qpath)
    problems = []

    if test["key_kind"] == "letters":
        letters = parse_letter_key(os.path.join(SRC_DIR, test["key"]))
        if len(letters) != len(questions):
            problems.append(f"key has {len(letters)} letters for "
                            f"{len(questions)} questions")
        else:
            for q, letter in zip(questions, letters):
                idx = ord(letter) - ord("A")
                for i, c in enumerate(q["choices"]):
                    c["is_correct"] = (i == idx)
                if not 0 <= idx < len(q["choices"]):
                    problems.append(f"letter {letter} out of range for "
                                    f"{len(q['choices'])} choices")

    kept, dropped = [], []
    for i, q in enumerate(questions, 1):
        n_correct = sum(c["is_correct"] for c in q["choices"])
        if len(q["choices"]) < 2 or n_correct != 1:
            dropped.append((i, len(q["choices"]), n_correct, q["text"][:70]))
        else:
            kept.append(q)

    if verbose:
        spread = collections.Counter(
            next(i for i, c in enumerate(q["choices"]) if c["is_correct"])
            for q in kept)
        print(f"\n### {test['title']}")
        print(f"  parsed {len(questions)} questions "
              f"(expected {test['expect']}), keeping {len(kept)}")
        print("  answer positions: "
              + ", ".join(f"{'ABCD'[i]}={spread.get(i, 0)}" for i in range(4)))
        for i, nc, ncor, stem in dropped:
            print(f"  !! dropped q{i}: {nc} choices, {ncor} marked correct :: {stem}")
        for p in problems:
            print(f"  !! {p}")
    return kept, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", action="store_true",
                    help="insert each quiz via insert_one_quiz.py")
    args = ap.parse_args()

    written = []
    for test in TESTS:
        kept, problems = build(test)
        if problems:
            print(f"  -> NOT written ({test['out']}): fix the key first")
            continue
        out = os.path.join(HERE, test["out"])
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"source_pk": test["source_pk"], "title": test["title"],
                       "questions": kept}, fh, indent=1, ensure_ascii=False)
        print(f"  -> wrote {test['out']} ({len(kept)} questions)")
        written.append(out)

    if args.load:
        for out in written:
            subprocess.run([sys.executable,
                            os.path.join(HERE, "insert_one_quiz.py"), out],
                           check=True)


if __name__ == "__main__":
    main()
