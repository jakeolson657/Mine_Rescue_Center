# Quiz pipeline

Turns the archived written-test PDFs (the `Written Tests` competition problems)
into interactive `Quiz` / `QuizQuestion` / `QuizChoice` rows. Previously lived in
a session scratchpad; moved here so it's durable and version-controlled.

Run everything from the repo root with the project venv, e.g.
`PYTHONUTF8=1 venv/Scripts/python.exe quiz_pipeline/load_all_quizzes.py`.
(`PYTHONUTF8=1` matters on Windows for the PDF text.)

## Dependencies

Local-only (like the docx→PDF tools, these are NOT in the production
`requirements.txt`): `pymupdf` (imported as `fitz`) and `pypdf`, used by the
extractor/loader/renderer to read and rasterize the test PDFs. Install into the
project venv with `pip install pymupdf pypdf`. `insert_one_quiz.py` — the only
script also run on the production server — imports neither, so prod needs nothing
extra.

## Files

**Engine (pure libraries, no Django):**
- `extractor.py` — general test→quiz extractor. Reads question/choice structure
  with per-choice metadata (text color, bold, highlight, trailing citation) and
  tries every answer-marking convention, keeping whichever makes each question
  have exactly one correct choice.
- `parts_extract.py` — diagram-based "parts identification" questions from
  Dräger/BioPak bench tests (exploded diagram + red-marked choice grid).
- `run_report.py` — `pair_docs()` matches each test doc to its answer doc by
  title-token overlap. Import is cheap; run as a script for a coverage report.

**Answer sources (the durable, hand-authored truth):**
- `scanned_quizzes.py` — hand-transcribed quizzes for fully-scanned (image-only)
  tests; answers read from each test's own key. Helpers `q()` / `qi()` (the
  latter attaches a parts diagram image).
- `text_quizzes.py` — programmatic quizzes for text-layer tests whose answer
  format the main extractor doesn't handle (filled-bullet keys, split Day-1/2
  letter keys).
- `pinned_quizzes.json` — **snapshot of quizzes that were validated and deployed
  but the current extractor can no longer re-derive** (e.g. self-highlight
  word-fill tests that parse to "0 choices"). This file *cannot* be regenerated
  from the PDFs — it's the source of truth for those quizzes. See the safety
  guard below.

**Orchestration:**
- `build_manual.py` — assembles `scanned_quizzes` + `text_quizzes` + inline
  packet quizzes into `manual_quizzes.json` (a generated, committed artifact).
- `load_all_quizzes.py` — the loader. Auto-extracts every test, then layers on
  `manual_quizzes.json` + `pinned_quizzes.json`, and writes the quizzes to the DB.
- `render_parts_images.py` — renders the exploded-diagram crops referenced by the
  parts questions into `media/quiz_images/`.
- `insert_one_quiz.py` — add/update ONE quiz from a small JSON file. **Preferred
  way to add a single quiz** — see below.

## Adding one quiz (preferred)

Do NOT run a full rebuild+redeploy just to add a quiz. Instead:

1. Author the quiz as JSON: `{ "source_pk": N, "title": "...", "questions": [
   {"text": "...", "choices": [{"text": "...", "is_correct": true/false}, ...],
   "image_rel": "quiz_images/foo.png"  // optional } ] }`.
2. If it has diagram images, add a spec to `render_parts_images.py` and run it.
3. `python quiz_pipeline/insert_one_quiz.py your_quiz.json` (idempotent
   `update_or_create` on the source_document; disconnects the image-delete signal
   so diagram files survive). Run the same script on prod to deploy just that quiz.
4. `dumpdata pages` → `pages/fixtures/pages_data.json`, commit.

## Full rebuild & the safety guard

`load_all_quizzes.py --load` deletes and rebuilds every Written-Tests quiz.
Because the extractor's output can drift from what's deployed (older code/manual
passes created quizzes it can no longer re-derive), the loader records every
deployed quiz's source-document up front and, before pruning, **aborts if the
rebuild wouldn't reproduce one of them** — printing `WOULD DROP …` and naming the
missing docs. Fix by pinning those docs in `pinned_quizzes.json` (snapshot them
from the DB). Pass `--allow-drop` to override intentionally.

Without `--load` the loader is a DRY run (rolls back; still prints the guard
warning). The generated `needs_answers.json` / `review.json` / `report.json` /
`produced_src_pks.json` are diagnostics and are git-ignored.
