"""Idempotently insert/update a SINGLE manual quiz from a small JSON file, without
touching any other quiz. Safe to run on prod: it does update_or_create on the
quiz's source_document, so it never disturbs the other Written-Tests quizzes and
generates its own non-colliding pks server-side.

Usage: python insert_one_quiz.py <quiz.json>
  quiz.json = {"source_pk": N, "title": "...", "questions": [
     {"text": "...", "choices": [{"text":"...","is_correct":bool}, ...],
      "image_rel": "quiz_images/foo.png"  # optional
     }, ...]}
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (config/)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.db.models.signals import post_delete
from pages.models import ProblemDocument, Quiz, QuizQuestion, QuizChoice, delete_image_on_question_delete

# Deleting the old questions on an update would fire the image-delete signal and
# wipe the diagram files this quiz points at. Disconnect it for the operation.
post_delete.disconnect(delete_image_on_question_delete, sender=QuizQuestion)

data = json.load(open(sys.argv[1], encoding='utf-8'))
src = ProblemDocument.objects.get(pk=data['source_pk'])
qs = [q for q in data['questions']
      if sum(c['is_correct'] for c in q['choices']) == 1
      and len([c for c in q['choices'] if c['text'].strip()]) >= 2]
assert len(qs) == len(data['questions']), 'some questions not single-correct/2-choice'

quiz, created = Quiz.objects.update_or_create(
    problem=src.problem, source_document=src, title=data['title'],
    defaults={'sort_order': 90})
quiz.questions.all().delete()
for qi, q in enumerate(qs):
    qq = QuizQuestion(quiz=quiz, text=q['text'], sort_order=qi)
    if q.get('image_rel'):
        qq.image.name = q['image_rel']
    qq.save()
    for ci, c in enumerate(q['choices']):
        QuizChoice.objects.create(question=qq, text=c['text'], is_correct=c['is_correct'], sort_order=ci)

bad = [x.id for x in quiz.questions.all() if sum(c.is_correct for c in x.choices.all()) != 1]
print(f"{'created' if created else 'updated'} quiz pk={quiz.pk} '{quiz.title}' "
      f"src={src.pk} questions={quiz.questions.count()} imgs={sum(1 for x in quiz.questions.all() if x.image)} malformed={len(bad)}")
print("total quizzes:", Quiz.objects.count())
