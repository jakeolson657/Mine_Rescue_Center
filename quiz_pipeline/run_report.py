"""pair_docs() matches each test doc to its answer doc by title-token overlap.
Importing this module is cheap (no Django); running it as a script generates the
coverage report (report.json). load_all_quizzes imports only pair_docs."""
import os, re, sys

ANSWER_WORDS = re.compile(r'\b(answers?|key|rationales?|solutions?)\b', re.I)

def norm_tokens(title):
    base = ANSWER_WORDS.sub('', title).lower()
    # Keep single-character DIGIT tokens ("Day 1" vs "Day 2") — they're the only
    # thing distinguishing per-day tests, and dropping them mis-paired a Day 2 test
    # with the Day 1 answer key. Still drop single letters and boilerplate words.
    return set(w for w in re.findall(r'[a-z0-9]+', base)
               if (len(w) > 1 or w.isdigit()) and w not in ('written', 'test', 'exam', 'the', 'and'))

def pair_docs(docs):
    """Return list of (test_doc, answer_doc_or_None). Answers matched to tests by
    token overlap, assigning the STRONGEST matches first (global, not in test
    order) so a weak shared token ("Apparatus Drager" ~ "Apparatus Biomarine
    Answers", overlap 1) can't steal an answer from the test that shares more
    ("Apparatus Biomarine", overlap 2)."""
    tests = [d for d in docs if not ANSWER_WORDS.search(d.title)]
    answers = [d for d in docs if ANSWER_WORDS.search(d.title)]
    triples = []
    for t in tests:
        tt = norm_tokens(t.title)
        for a in answers:
            s = len(tt & norm_tokens(a.title))
            if s >= 1:
                triples.append((s, t, a))
    triples.sort(key=lambda x: -x[0])
    t2a, used = {}, set()
    for s, t, a in triples:
        if t.pk in t2a or a.pk in used:
            continue
        t2a[t.pk] = a
        used.add(a.pk)
    pairs = []
    for t in tests:
        a = t2a.get(t.pk)
        # a lone test and a lone answer doc that share no distinctive token
        # ("Written Test" / "Written Test Answers") still pair.
        if a is None and len(tests) == 1 and len(answers) == 1 and answers[0].pk not in used:
            a = answers[0]
            used.add(a.pk)
        pairs.append((t, a))
    orphan_answers = [a for a in answers if a.pk not in used]
    return pairs, orphan_answers

if __name__ == '__main__':
    import json
    import django
    _HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _HERE)
    sys.path.insert(0, os.path.dirname(_HERE))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from pages.models import CompetitionProblem
    import extractor

    report = []
    clean_count = 0
    needs_answers = []
    review = []

    for wt in CompetitionProblem.objects.filter(title='Written Tests').select_related('competition').order_by('-competition__year', 'competition__name'):
        docs = list(wt.documents.all())
        pairs, orphans = pair_docs(docs)
        prob = {'year': wt.competition.year, 'competition': wt.competition.name, 'problem_pk': wt.pk, 'tests': []}
        for test_doc, answer_doc in pairs:
            res = extractor.extract(test_doc.file.name, answer_doc.file.name if answer_doc else None)
            status = 'clean' if res.get('clean') else ('review' if res['questions'] else 'no-parse')
            n_q = len(res['questions']) if res['questions'] else 0
            rec = {
                'test_pk': test_doc.pk, 'test_title': test_doc.title,
                'answer_title': answer_doc.title if answer_doc else None,
                'method': res['method'], 'n_questions': n_q,
                'status': status, 'issues': res['issues'][:6],
            }
            prob['tests'].append(rec)
            if status == 'clean':
                clean_count += 1
            elif answer_doc is None and status != 'clean':
                needs_answers.append((wt.competition.year, wt.competition.name, test_doc.title))
            else:
                review.append((wt.competition.year, wt.competition.name, test_doc.title, res['method'], res['issues'][:3]))
        prob['orphan_answers'] = [a.title for a in orphans]
        report.append(prob)

    with open(os.path.join(_HERE, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    total_tests = sum(len(p['tests']) for p in report)
    print(f"Problems: {len(report)}   Test docs: {total_tests}")
    print(f"CLEAN (auto-extractable): {clean_count}")
    print(f"NEEDS ANSWERS (no answer doc, couldn't self-extract): {len(needs_answers)}")
    print(f"REVIEW (has answer source but didn't validate): {len(review)}")
    print()
    from collections import Counter
    methods = Counter(t['method'] for p in report for t in p['tests'])
    print("methods:", dict(methods))
