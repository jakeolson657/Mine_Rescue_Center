"""Fold the separate written-test answer-key rows into Key buttons.

Before the Key button existed (ProblemDocument.answer_key), keys were imported
as their own document rows, e.g. "Day 1 Written Test Answers" next to
"Day 1 Written Test". This moves each such key onto its test's answer_key and
removes the separate row, keeping the PDF on disk.

Pairing:
  * Title rule: a row titled "<test> Answers" / "<test> Key" /
    "<test> - Key" / "<test> Answer Key" pairs with the one sibling titled
    exactly "<test>" in the same problem.
  * 2021 practice exams: "With Answers (n)" rows pair by file name
    (Test_1_05102021.pdf -> Test_1_05102021_withanswers.pdf, ...).
  * 2022 Fallen Heroes: the one-page "key for both days" was split into
    per-day halves (..._Day_One_Test_Key.pdf / ..._Day_Two_Test_Key.pdf, which
    must already be in media/problems); each goes on its own test.

Also deletes the 2014 "... Written Test Answer Sheet" rows: blank bubble forms
for contestants, not keys (their real keys are paired above).

Refuses to run if any pairing is ambiguous, a test already has a key, or a key
row is a quiz's source document. Idempotent: a second run finds nothing to do.

Run:  python local_2026_ingest/attach_answer_keys.py        (--dry-run to preview)
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402
from django.db.models.signals import post_delete  # noqa: E402
from pages.models import (  # noqa: E402
    ProblemDocument, Quiz, delete_file_on_document_delete,
)

KEY_SUFFIX = re.compile(r"\s*(?:-\s*)?(?:answer key|answers|key)\s*$", re.I)
PRACTICE_PREFIX = "problems/2021_practice_Practice_Written_Exams_"
PRACTICE_KEY_STEMS = {  # test file stem -> key file stem
    "Test_1_05102021": "Test_1_05102021_withanswers",
    "Test_2_05102021": "Test_2_05102021_withanswers",
    "Problem1writtenexam_June72021": "Problem1writtenexam_June72021_withanswers",
    "Problem2writtenexam_June72021": "Problem2writtenexam_June72021_withanswers",
    "Problem3writtenexam_June72021": "Problem3writtenexam_June72021with_answers",
}
HEROES = "problems/2022_Heroes_Written_Examinations_Fallen_Heroes_"
HEROES_COMBINED = HEROES + "TEST_KEY_FOR_BOTH_DAYS.pdf"
HEROES_SPLIT = {  # test file -> split key file
    HEROES + "Day_One_Test.pdf": HEROES + "Day_One_Test_Key.pdf",
    HEROES + "Day_Two_Test.pdf": HEROES + "Day_Two_Test_Key.pdf",
}


def plan():
    """Return (pairs, extra_keys, deletes): pairs are (test, key_row);
    extra_keys are (test, file_name) for keys with no row of their own;
    deletes are rows removed together with their file."""
    docs = list(ProblemDocument.objects.select_related("problem"))
    by_file = {d.file.name: d for d in docs}
    pairs, extra_keys, deletes, problems = [], [], [], []

    for d in docs:
        t = d.title.lower()
        if "answer sheet" in t:
            if "written test" in t and d.problem.title == "Written Tests":
                deletes.append(d)
            continue
        if "map" in t or not KEY_SUFFIX.search(d.title):
            continue
        base = KEY_SUFFIX.sub("", d.title).strip().lower()
        tests = [s for s in d.problem.documents.all() if s.pk != d.pk and s.title.strip().lower() == base]
        if len(tests) == 1:
            pairs.append((tests[0], d))
        elif not d.title.lower().startswith("with answers") and d.file.name != HEROES_COMBINED:
            problems.append(f"no single test for key {d.pk} {d.title!r} ({len(tests)} matches)")

    for test_stem, key_stem in PRACTICE_KEY_STEMS.items():
        test = by_file.get(f"{PRACTICE_PREFIX}{test_stem}.pdf")
        key = by_file.get(f"{PRACTICE_PREFIX}{key_stem}.pdf")
        if test and key:
            pairs.append((test, key))
        elif key:
            problems.append(f"practice key {key.pk} has no test row")

    combined = by_file.get(HEROES_COMBINED)
    if combined:
        for test_file, key_file in HEROES_SPLIT.items():
            test = by_file.get(test_file)
            if not test:
                problems.append(f"missing Fallen Heroes test {test_file}")
            elif not os.path.exists(os.path.join(settings.MEDIA_ROOT, key_file)):
                problems.append(f"missing split key file {key_file}")
            else:
                extra_keys.append((test, key_file))

    quiz_sources = set(Quiz.objects.values_list("source_document_id", flat=True))
    tests = [t for t, _ in pairs] + [t for t, _ in extra_keys]
    for t in tests:
        if t.answer_key:
            problems.append(f"test {t.pk} {t.title!r} already has a key")
        if tests.count(t) > 1:
            problems.append(f"test {t.pk} {t.title!r} paired twice")
    for _, k in pairs:
        if k.pk in quiz_sources:
            problems.append(f"key {k.pk} {k.title!r} is a quiz source document")
    return pairs, extra_keys, deletes, combined, sorted(set(problems))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pairs, extra_keys, deletes, combined, problems = plan()
    for test, key in pairs:
        print(f"key {key.pk:>5} {key.title!r} -> test {test.pk} {test.title!r} [problem {test.problem_id}]")
    for test, key_file in extra_keys:
        print(f"split key {key_file} -> test {test.pk} {test.title!r}")
    if combined:
        print(f"remove combined key row {combined.pk} {combined.title!r}")
    for d in deletes:
        print(f"delete blank sheet {d.pk} {d.title!r}")
    print(f"\n{len(pairs)} keys + {len(extra_keys)} split keys attached, "
          f"{len(deletes)} blank sheets deleted")
    if problems:
        print("\nREFUSING — fix these first:\n  " + "\n  ".join(problems))
        sys.exit(1)
    if args.dry_run:
        return

    with transaction.atomic():
        for test, key in pairs:
            test.answer_key.name = key.file.name
            test.save(update_fields=["answer_key"])
        for test, key_file in extra_keys:
            test.answer_key.name = key_file
            test.save(update_fields=["answer_key"])
        # The key rows' files now belong to the tests, so delete those rows
        # without the signal that would delete the files with them.
        post_delete.disconnect(delete_file_on_document_delete, sender=ProblemDocument)
        try:
            for _, key in pairs:
                key.delete()
            if combined:
                combined.delete()
        finally:
            post_delete.connect(delete_file_on_document_delete, sender=ProblemDocument)
        for d in deletes:
            d.delete()  # signal removes the blank sheet's file too
    print("done")


if __name__ == "__main__":
    main()
