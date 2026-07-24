import django, os, re, sys, json
from collections import Counter
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                    # sibling pipeline modules
sys.path.insert(0, os.path.dirname(_HERE))   # repo root (config/, pages/)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import fitz
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
from pages.models import CompetitionProblem, ProblemDocument, Quiz, QuizQuestion, QuizChoice
from django.db.models.signals import post_delete
from pages.models import delete_image_on_question_delete
# A full rebuild deletes every quiz question, and QuizQuestion's post_delete
# signal would delete each question's diagram FILE with it. Parts questions point
# at stable pre-rendered images (manual ones from render_parts_images.py; pipeline
# ones re-rendered below), so deleting the files just breaks them. Disconnect the
# signal for the duration of the load so the images survive the rebuild.
post_delete.disconnect(delete_image_on_question_delete, sender=QuizQuestion)
import extractor
import parts_extract
from run_report import pair_docs

DRY = '--load' not in sys.argv
# residual leak: a TRAILING parenthetical/bracket citation still on the answer
# (clean_text should have removed these; this only catches ones it missed). Must
# be trailing so a legit mid-answer parenthetical like "(... under 42 CFR Part
# 84, Subpart H), and ..." isn't mistaken for an appended citation marker.
leak_re = re.compile(
    r'[\(\[][^)\]]*(?:\bpp?\.?\s*\d|\bpages?\b|\bpg\b|cfr|\bbrady\b|\bmodules?\b|¶)[^)\]]*[\)\]]?\s*$', re.I)

IMG_DIR = os.path.join(settings.MEDIA_ROOT, 'quiz_images')


def key_letter(value):
    """Pull the A-E answer letter out of an embedded-key value. Handles a bare
    leading letter ("B", "B pg. 1-3") and a letter embedded after a label
    ("Cooling Canister B- Cover", "Statement #5 Page 13 C- Zero")."""
    v = str(value).strip()
    m = re.match(r'^\(?([A-Ea-e])(?:[\.\)\-]|\s|$)', v)
    if m:
        return m.group(1).upper()
    m = re.search(r'(?:^|\s)([A-Ea-e])\s*[-–]', v)  # letter directly before a dash
    return m.group(1).upper() if m else ''


def parts_questions_for(parts_doc, answer_key=None):
    """Diagram-based parts questions from a doc: each returns
    {'text', 'choices':[{text,is_correct}], 'image_rel'} with the diagram
    rendered to media/quiz_images/. Correct answers come from the grid's red
    marking, or from `answer_key` ({question_number: letter}) when the answers
    live in an embedded key instead. Returns [] if the doc has no parts pages."""
    path = os.path.join(settings.MEDIA_ROOT, parts_doc.file.name)
    try:
        doc = fitz.open(path)
    except Exception:
        return []
    out = []
    base = slugify(os.path.splitext(os.path.basename(parts_doc.file.name))[0])[:60]
    for pi in range(len(doc)):
        qs, clip = parts_extract.extract_parts_page(doc[pi], answer_key=answer_key)
        qs = [q for q in qs if sum(c['is_correct'] for c in q['choices']) == 1]
        if not qs:
            continue
        image_rel = None
        if not DRY:
            os.makedirs(IMG_DIR, exist_ok=True)
            fname = f'{base}_p{pi + 1}.png'
            doc[pi].get_pixmap(clip=clip, dpi=150).save(os.path.join(IMG_DIR, fname))
            image_rel = f'quiz_images/{fname}'
        for q in qs:
            out.append({
                'text': q['stem'] or f"Part {q['num']}",
                'choices': [{'text': c['text'], 'is_correct': c['is_correct']} for c in q['choices']],
                'image_rel': image_rel,
            })
    return out


def key_based(method):
    """True when the answers came from an authoritative source — a separate answer
    key doc, an embedded end-of-doc key, a numbered answer list, or a word key —
    rather than being inferred from self-marking (bold/citation/text-color) on the
    test itself. A skewed answer distribution from such a source is the test's real
    answer pattern, not a detector artifact, so the skew guardrail shouldn't fire."""
    return bool(method) and method.split('/')[0] in (
        'key', 'embedded-key', 'separate-list', 'statement-of-fact',
        'sof-highlight', 'true-false', 'true-false-mixed')


def dedupe_choices(q):
    """Drop wrong choices whose text is identical to the correct choice's text.
    Some source tests literally list the answer twice (e.g. "carotid" as both a
    distractor and the keyed answer); the duplicate is redundant and reads as an
    ambiguous second-correct, so removing it is always safe — it never changes
    which answer is right."""
    corr = next((c for c in q['choices'] if c['is_correct']), None)
    if not corr:
        return
    ct = corr['text'].strip().lower()
    if not ct:
        return
    kept = []
    for c in q['choices']:
        if not c['is_correct'] and c['text'].strip().lower() == ct:
            continue
        kept.append(c)
    q['choices'] = kept


def sanity_flags(qs, method):
    flags = []
    kb = key_based(method)
    positions = [next((i for i, c in enumerate(q['choices']) if c['is_correct']), -1) for q in qs]
    dist = Counter(positions)
    # Skew checks only apply to inferred (self-marking) answers; an authoritative
    # key legitimately can put every answer in the same column.
    if not kb and len(qs) >= 5 and len(dist) == 1:
        flags.append('all-one-position')
    if not kb and len(qs) >= 8 and dist.most_common(1)[0][1] / len(qs) > 0.85:
        flags.append('one-position-dominant')
    for i, q in enumerate(qs):
        texts = [c['text'] for c in q['choices']]
        if len([t for t in texts if t.strip()]) < 2:
            flags.append(f'q{i+1}-fewchoices')
        # Only a duplicated CORRECT answer is a problem (ambiguous which to pick).
        # Duplicated wrong distractors are harmless — that's how the test reads.
        correct_l = [c['text'].strip().lower() for c in q['choices'] if c['is_correct']]
        if correct_l and [t.strip().lower() for t in texts].count(correct_l[0]) > 1:
            flags.append(f'q{i+1}-dupcorrect')
        correct = [c['text'] for c in q['choices'] if c['is_correct']][0]
        if leak_re.search(correct) and not any(leak_re.search(c['text']) for c in q['choices'] if not c['is_correct']):
            flags.append(f'q{i+1}-leak')
    # Bold-marked answers are allowed to load when they validate cleanly and pass
    # the skew/dup checks above (verified bold reliably marks the answer on these
    # tests); no blanket bold-hold.
    return flags


loaded = []
produced_pks = set()  # Quiz pks (re)used this run; anything else under Written
                      # Tests is stale and pruned at the end. Reusing rows keeps
                      # quiz pks — and thus the public /problems/quiz/<pk>/ URLs —
                      # STABLE across rebuilds instead of churning every load.
needs_answers = []   # (year, comp, test title) - no answer doc & couldn't self-extract
review = []          # (year, comp, test title, reason) - has answers but not clean/sane

problems = CompetitionProblem.objects.filter(title='Written Tests').select_related('competition').order_by('-competition__year', 'competition__name')

# Safety baseline: the source_documents that already have a deployed quiz. A full
# rebuild must reproduce every one of these; if it wouldn't, that's silent data
# loss (see the 2016-2018 self-highlight tests that the extractor can't re-derive
# and which are therefore pinned in pinned_quizzes.json). The guard below aborts
# rather than prune them away.
pre_existing_src = set(Quiz.objects.filter(problem__title='Written Tests').values_list('source_document_id', flat=True))

with transaction.atomic():
    for wt in problems:
        docs = list(wt.documents.all())
        pairs, _ = pair_docs(docs)
        for si, (test_doc, answer_doc) in enumerate(pairs):
            # Find the doc holding a diagram-based parts section (the answer doc,
            # or the test doc itself when it's self-contained). Stop the linear
            # extraction before that section so parts pages don't bleed into the
            # last multiple-choice question.
            parts_doc, parts_start = None, None
            for cand in (answer_doc, test_doc):
                if not cand:
                    continue
                try:
                    fp = parts_extract.first_parts_page(
                        fitz.open(os.path.join(settings.MEDIA_ROOT, cand.file.name)))
                except Exception:
                    fp = None
                if fp is not None:
                    parts_doc, parts_start = cand, fp
                    break

            # When the parts answers live in an embedded answer key (rather than
            # red grid marking), read that key so the parts choices can be marked.
            embedded_key = None
            if parts_doc:
                try:
                    kp = extractor.find_answer_key_page(
                        os.path.join(settings.MEDIA_ROOT, parts_doc.file.name))
                    if kp:
                        raw_key = extractor.parse_answer_list(
                            os.path.join(settings.MEDIA_ROOT, parts_doc.file.name), start_page=kp)
                        # Only trust the key for parts marking when it's a CLEAN
                        # letter key (values are bare A-E letters, like "B" /
                        # "B pg. 1-3"). Irregular keys ("Cooling Canister B- Cover")
                        # can't be trusted to align a marker number to an answer.
                        bare = sum(1 for v in raw_key.values()
                                   if re.match(r'^\(?[A-Ea-e](?:[\.\):\-\s]|$)', str(v).strip()))
                        if raw_key and bare >= 0.8 * len(raw_key):
                            embedded_key = {k: key_letter(v) for k, v in raw_key.items() if key_letter(v)}
                except Exception:
                    embedded_key = None

            res = extractor.extract(test_doc.file.name,
                                    answer_doc.file.name if answer_doc else None,
                                    max_pages=parts_start)
            # Drop stray empty-text choices (a parse artifact, e.g. a True/False
            # question with a blank third option), then re-validate: if dropping
            # broke a question (lost its correct choice or left <2), it's no
            # longer clean and won't load.
            orig_clean = res.get('clean')
            if res.get('questions'):
                for q in res['questions']:
                    q['choices'] = [c for c in q['choices'] if c['text'].strip()]
                    dedupe_choices(q)
                if res.get('clean') and extractor.validate(res['questions']):
                    res['clean'] = False
            clean = res.get('clean')
            # Authoritative-key salvage: when the answers come from a real key
            # (separate answer doc, embedded end-of-doc key, numbered list, word
            # key) and the vast majority of questions already resolved to exactly
            # one keyed answer, drop the few that didn't and keep the rest. Those
            # stragglers are per-question parse hiccups (a choice that collapsed
            # after citation-stripping, or a genuine multi-answer "A,B,&C" item
            # that can't be single-correct) — the key vouches for every other
            # answer, so recovering the quiz beats failing it over a handful.
            # Safe because it only fires at >=80% single-correct: a truly
            # misaligned key leaves most questions unmatched and won't qualify.
            if not clean and key_based(res['method']) and res['questions']:
                good = [q for q in res['questions']
                        if len(q['choices']) >= 2 and sum(c['is_correct'] for c in q['choices']) == 1]
                if len(good) >= 5 and len(good) >= 0.8 * len(res['questions']):
                    res['questions'] = good
                    clean = True
            flags = sanity_flags(res['questions'], res['method']) if clean else ['not-clean']

            # Diagram-based "parts identification" questions the linear extractor
            # can't handle — recovered separately, each carrying its diagram image.
            parts = parts_questions_for(parts_doc, answer_key=embedded_key) if parts_doc else []
            # Parts bypass the normal validation, so sanity-check them here and
            # drop the whole parts section if it looks wrong (e.g. every answer in
            # the same position from a mis-parsed key) — keep the good MC section.
            if parts and sanity_flags(parts, 'parts'):
                parts = []

            linear = res['questions'] if (clean and not flags) else []

            if linear or parts:
                combined = list(linear) + parts
                loaded.append((wt, test_doc, {'questions': combined, 'method': res['method'], 'parts': len(parts)}))
                if not DRY:
                    # Reuse the existing quiz row (keeps its pk/URL stable); only
                    # its questions are rebuilt. update_or_create matches on
                    # problem+source_document+title.
                    quiz, _ = Quiz.objects.update_or_create(
                        problem=wt, source_document=test_doc, title=test_doc.title,
                        defaults={'sort_order': si})
                    produced_pks.add(quiz.pk)
                    quiz.questions.all().delete()
                    for qi, q in enumerate(combined):
                        qq = QuizQuestion(quiz=quiz, text=q['text'], sort_order=qi)
                        if q.get('image_rel'):
                            qq.image.name = q['image_rel']
                        qq.save()
                        for ci, c in enumerate(q['choices']):
                            QuizChoice.objects.create(question=qq, text=c['text'], is_correct=c['is_correct'], sort_order=ci)
            elif answer_doc is None and not clean:
                needs_answers.append((wt.competition.year, wt.competition.name, test_doc.title))
            else:
                reason = ','.join(flags) if clean else (res['method'] or 'no-parse')
                review.append((wt.competition.year, wt.competition.name, test_doc.title, reason))

    # Manual supplements: quizzes hand-built from multi-test PACKET documents that
    # the linear pipeline can't split (e.g. 2013 NMRA Post 2 "Bench Written Test"
    # bundles a BioMarine 240R test + a Kentucky Post 2 test + parts diagrams in one
    # PDF). Each entry is one quiz on an existing source_document, already validated
    # against its printed key.
    # manual_quizzes.json: quizzes hand-built from PACKET docs (build_manual.py).
    # pinned_quizzes.json: quizzes that WERE deployed and validated but the current
    # extractor can no longer re-derive (e.g. self-highlight word-fill tests that
    # parse to "0 choices"). Snapshotted from the DB so a rebuild reproduces them
    # exactly instead of dropping them. Both are single-correct manual supplements.
    manual = []
    for fname in ('manual_quizzes.json', 'pinned_quizzes.json'):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                manual += json.load(f)
    for mq in manual:
        src = ProblemDocument.objects.filter(pk=mq['source_pk']).first()
        if not src:
            continue
        qs = [q for q in mq['questions'] if sum(c['is_correct'] for c in q['choices']) == 1
              and len([c for c in q['choices'] if c['text'].strip()]) >= 2]
        if not qs:
            continue
        loaded.append((src.problem, src, {'questions': qs, 'method': 'manual', 'parts': 0}))
        if not DRY:
            quiz, _ = Quiz.objects.update_or_create(
                problem=src.problem, source_document=src, title=mq['title'],
                defaults={'sort_order': 90})
            produced_pks.add(quiz.pk)
            quiz.questions.all().delete()
            for qi, q in enumerate(qs):
                qq = QuizQuestion(quiz=quiz, text=q['text'], sort_order=qi)
                if q.get('image_rel'):        # parts-ID questions carry a diagram
                    qq.image.name = q['image_rel']
                qq.save()
                for ci, c in enumerate(q['choices']):
                    QuizChoice.objects.create(question=qq, text=c['text'], is_correct=c['is_correct'], sort_order=ci)

    # SAFETY GUARD: never let a rebuild silently drop a deployed quiz. If any
    # source_document that had a quiz before this run wasn't reproduced, abort
    # (rolls back the transaction) and name the missing docs, unless --allow-drop
    # is passed explicitly. Pin such docs in pinned_quizzes.json instead.
    produced_src = {doc.pk for _, doc, _ in loaded}
    dropped_src = pre_existing_src - produced_src
    if dropped_src:
        from pages.models import ProblemDocument as _PD
        print(f"\n!! WOULD DROP {len(dropped_src)} deployed quiz(zes) — rebuild NOT reproducing them:")
        for spk in sorted(dropped_src):
            d = _PD.objects.filter(pk=spk).select_related('problem__competition').first()
            if d:
                print(f"   src={spk} {d.problem.competition.year} {d.problem.competition.name} | {d.title!r}")
        if not DRY and '--allow-drop' not in sys.argv:
            print("ABORTING load (pass --allow-drop to override, or pin these in pinned_quizzes.json).")
            raise SystemExit(1)
        print("(DRY run — would abort a real load)" if DRY else "(--allow-drop set — proceeding)")

    # Prune any Written-Tests quiz not (re)produced this run — a doc that stopped
    # yielding a quiz, or an old title. Reused rows kept their pks above; this only
    # removes genuine leftovers, so live quiz URLs stay stable.
    if not DRY:
        stale = Quiz.objects.filter(problem__title='Written Tests').exclude(pk__in=produced_pks)
        n_stale = stale.count()
        stale.delete()
        if n_stale:
            print(f"pruned {n_stale} stale quiz(es)")

    if DRY:
        transaction.set_rollback(True)

print(('DRY RUN — ' if DRY else 'LOADED — ') + f"{len(loaded)} quizzes, {sum(len(r['questions']) for _,_,r in loaded)} questions")
print(f"needs-answers: {len(needs_answers)}   review: {len(review)}")

# Diagnostic outputs (git-ignored): what this run produced / couldn't answer.
with open(os.path.join(_HERE, 'produced_src_pks.json'), 'w') as f:
    json.dump(sorted({doc.pk for _, doc, _ in loaded}), f)
with open(os.path.join(_HERE, 'needs_answers.json'), 'w') as f:
    json.dump(needs_answers, f, indent=2)
with open(os.path.join(_HERE, 'review.json'), 'w') as f:
    json.dump(review, f, indent=2)
