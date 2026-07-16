import os
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


class SiteConfiguration(models.Model):
    """Site-wide settings editable from the admin. A single row (pk=1); use
    ``SiteConfiguration.load()`` to read it."""

    msha_calendar_url = models.URLField(
        "MSHA calendar link",
        max_length=500,
        blank=True,
        help_text="URL for the “Official MSHA Contest Calendar” button "
                  "on the Competition Calendar page. Update it when MSHA posts "
                  "the next season’s contest page. Leave blank to hide the "
                  "button.",
    )

    class Meta:
        verbose_name = "Site configuration"
        verbose_name_plural = "Site configuration"

    def __str__(self):
        return "Site configuration"

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce a single row
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CalendarEvent(models.Model):
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    contact_info = models.TextField(blank=True)
    resources = models.JSONField(
        default=list, blank=True,
        help_text="Links to results, registration forms, flyers, etc. "
                  "Format: [{\"label\": \"Final Results\", \"url\": \"https://...\"}, ...]",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        if self.start_date == self.end_date:
            return f"{self.title} - {self.start_date}"
        return f"{self.title} - {self.start_date} to {self.end_date}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1


# Words that appear in nearly every event title and therefore can't serve as
# the *only* evidence for a match. They still count toward name coverage —
# "Missouri Regional Mine Rescue Contest" vs "Missouri Regional Skills Contest"
# is decided by exactly these words.
MATCH_STOPWORDS = {
    'mine', 'rescue', 'regional', 'national', 'nationals', 'competition',
    'contest', 'contests', 'championship', 'annual',
}

# Short forms calendar entries use for words people write out in competition
# names. Aliases are matched on word boundaries so 'ug' can't hit 'august'.
WORD_ALIASES = {
    'underground': ('ug',),
}


def _name_tokens(name):
    """All meaningful words from a competition name (stopwords included —
    coverage counting needs the full name)."""
    return {
        token for token in re.findall(r'[a-z]+', name.lower())
        if len(token) >= 4
    }


def _hits(tokens, text):
    score = 0
    for token in tokens:
        if token in text:
            score += 1
            continue
        for alias in WORD_ALIASES.get(token, ()):
            if re.search(rf'\b{re.escape(alias)}\b', text):
                score += 1
                break
    return score


US_STATES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
    'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE',
    'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
    'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
    'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR',
    'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
}
_STATE_ABBRS = set(US_STATES.values())


def short_location(full):
    """Collapse a full venue string to just "City, ST".

    Calendar entries store the venue plus city, state, and sometimes a street
    and ZIP (e.g. "Winnemucca Convention Center, 50 W Winnemucca Blvd,
    Winnemucca, NV 89445"). The past-problems list only wants the city and the
    two-letter state. The state is the last comma-separated piece (possibly a
    spelled-out name or trailed by a ZIP) and the city is the piece before it.
    Returns the original string unchanged when it can't be parsed."""
    parts = [p.strip() for p in (full or '').split(',') if p.strip()]
    if len(parts) < 2:
        return full or ''
    city, tail = parts[-2], parts[-1]
    tokens = tail.split()
    state = None
    if tokens and len(tokens[0]) == 2 and tokens[0].upper() in _STATE_ABBRS:
        state = tokens[0].upper()           # "NV" or "NV 89445"
    else:
        # Drop a trailing ZIP, then look up the spelled-out state name.
        name = re.sub(r'\s+\d{5}(?:-\d{4})?$', '', tail).strip().lower()
        state = US_STATES.get(name)
    if not state:
        return full or ''
    return f"{city}, {state}"


class Competition(models.Model):
    name = models.CharField(max_length=200, help_text="e.g. Loveland, Colorado")
    year = models.PositiveIntegerField(null=True, blank=True)
    calendar_event = models.ForeignKey(
        CalendarEvent, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='competitions',
        help_text="Calendar entry for this competition. Matched automatically "
                  "within the same year by comparing this competition's name "
                  "to event titles and locations; set it here to override.",
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'name']

    def __str__(self):
        if self.year:
            return f"{self.name} ({self.year})"
        return self.name

    def problem_count(self):
        return self.problems.count()

    @property
    def start_date(self):
        return self.calendar_event.start_date if self.calendar_event else None

    @property
    def location(self):
        return self.calendar_event.location if self.calendar_event else ''

    @property
    def short_location(self):
        """City + abbreviated state for the past-problems list (no venue). The
        full venue stays on the calendar via ``location``."""
        return short_location(self.location)

    def find_calendar_event(self):
        """Match the competition NAME against calendar events in the same year.
        The name is compared word-by-word to each event's title + location: at
        least two-thirds of the name's words must appear there, including one
        distinctive word (a name made only of generic words like 'Mine Rescue
        Contest' never links). The event matching the most words wins, so
        naming a competition after the calendar title links it directly, and
        place-style names ('Loveland, Colorado') still match via the location.
        Returns None when nothing qualifies or the leaders tie (never guesses)."""
        if not self.year:
            return None
        tokens = _name_tokens(self.name)
        distinctive = tokens - MATCH_STOPWORDS
        if not tokens or not distinctive:
            return None
        best, best_matched, tied = None, 0, False
        for event in CalendarEvent.objects.filter(start_date__year=self.year):
            text = f"{event.title} {event.location}".lower()
            matched = _hits(tokens, text)
            if matched * 3 < len(tokens) * 2 or not _hits(distinctive, text):
                continue
            if matched > best_matched:
                best, best_matched, tied = event, matched, False
            elif matched == best_matched:
                tied = True
        if tied:
            return None
        return best

    def save(self, *args, **kwargs):
        if self._state.adding and self.calendar_event_id is None:
            self.calendar_event = self.find_calendar_event()
        if self.year is None and self.calendar_event_id:
            self.year = self.calendar_event.start_date.year
        super().save(*args, **kwargs)


# Problem-type filters shown on the past-problems page, in display order.
# (slug, label) — the slug is emitted as a data attribute for the client-side
# filter and the label is the chip text.
PROBLEM_CATEGORIES = [
    ('coal', 'Coal'),
    ('mnm', 'MNM'),
    ('bench', 'Bench'),
    ('first-aid', 'First Aid'),
    ('preshift', 'Preshift'),
    ('written', 'Written Test'),
]

# Event-type categories are named in the problem title (e.g. "First Aid",
# "Preshift", "Bench", "Written Exams").
_TITLE_KEYWORDS = {
    'bench': ('bench',),
    'first-aid': ('first aid', 'first-aid'),
    'preshift': ('preshift', 'pre-shift'),
    'written': ('written',),
}
# Coal vs. metal/nonmetal is the mine type, which applies to the whole contest:
# the underground field problem is usually just titled "Mine Rescue", so these
# also match the competition name.
_TITLE_OR_COMP_KEYWORDS = {
    'coal': ('coal',),
    'mnm': ('mnm', 'nonmetal', 'non-metal', 'metal', 'm/nm', 'n/m'),
}

_CATEGORY_ORDER = [slug for slug, _ in PROBLEM_CATEGORIES]


def categorize_problem(title, competition_name=''):
    """Return the list of category slugs that apply to a problem, in display
    order. Used to tag each problem for the client-side discipline filter."""
    title_text = (title or '').lower()
    comp_text = (competition_name or '').lower()
    slugs = set()
    for slug, keywords in _TITLE_KEYWORDS.items():
        if any(k in title_text for k in keywords):
            slugs.add(slug)
    for slug, keywords in _TITLE_OR_COMP_KEYWORDS.items():
        if any(k in title_text or k in comp_text for k in keywords):
            slugs.add(slug)
    return [slug for slug in _CATEGORY_ORDER if slug in slugs]


class CompetitionProblem(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='problems')
    title = models.CharField(max_length=200, help_text="e.g. Coal Day 1, Nonmetal Day 2, Bench, First Aid")
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0, help_text="Problems are listed lowest number first")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        if self.competition_id:
            return f"{self.competition.name} - {self.title}"
        return self.title

    def document_count(self):
        return self.documents.count()


PREVIEW_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
PREVIEW_FRAME_EXTENSIONS = {'.pdf', '.txt'}


def preview_kind_for(filename):
    """'image', 'frame' (PDF/text rendered in an iframe), or '' when the
    browser can't display the file type inline."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in PREVIEW_IMAGE_EXTENSIONS:
        return 'image'
    if ext in PREVIEW_FRAME_EXTENSIONS:
        return 'frame'
    return ''


class ProblemDocument(models.Model):
    problem = models.ForeignKey(CompetitionProblem, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255, help_text="Document type or name, e.g. Problem, Layout, Vent Plan 1")
    file = models.FileField(upload_to='problems/')
    sort_order = models.PositiveIntegerField(default=0, help_text="Documents are listed lowest number first")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return f"{self.problem.title} - {self.title}"

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def preview_kind(self):
        return preview_kind_for(self.file.name)


@receiver(post_delete, sender=ProblemDocument)
def delete_file_on_document_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


class InstructionGuide(models.Model):
    """MSHA mine rescue instruction guides (IGs) — training curricula, e.g.
    IG 115 or MSHA 3026."""
    title = models.CharField(max_length=255, help_text="e.g. Unified Mine Rescue Training (Advanced) — IG 115")
    description = models.TextField(help_text="What this guide covers and who it's for")
    file = models.FileField(upload_to='training/igs/')
    sort_order = models.PositiveIntegerField(default=0, help_text="Guides are listed lowest number first")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def preview_kind(self):
        return preview_kind_for(self.file.name)


@receiver(post_delete, sender=InstructionGuide)
def delete_file_on_instruction_guide_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


class CompetitionRuleDocument(models.Model):
    """MSHA unified mine rescue competition rules — one row per rule section
    or supporting document (Q&A, preshift record report, etc.)."""
    title = models.CharField(max_length=255, help_text="e.g. Section I: Coal Mine Rescue Rules")
    file = models.FileField(upload_to='training/rules/')
    sort_order = models.PositiveIntegerField(default=0, help_text="Documents are listed lowest number first")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def preview_kind(self):
        return preview_kind_for(self.file.name)


@receiver(post_delete, sender=CompetitionRuleDocument)
def delete_file_on_rule_document_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


class FirstAidResource(models.Model):
    """A first aid training document (guides, protocols, references)."""
    title = models.CharField(max_length=255, help_text="e.g. First Aid Field Reference")
    description = models.TextField(blank=True, help_text="What this document covers")
    file = models.FileField(upload_to='training/first_aid/')
    sort_order = models.PositiveIntegerField(default=0, help_text="Documents are listed lowest number first")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def preview_kind(self):
        return preview_kind_for(self.file.name)


@receiver(post_delete, sender=FirstAidResource)
def delete_file_on_first_aid_resource_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


class RopeRescueResource(models.Model):
    """A rope rescue training document (guides, rigging references, etc.)."""
    title = models.CharField(max_length=255, help_text="e.g. High Angle Rope Rescue Guide")
    description = models.TextField(blank=True, help_text="What this document covers")
    file = models.FileField(upload_to='training/rope_rescue/')
    sort_order = models.PositiveIntegerField(default=0, help_text="Documents are listed lowest number first")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def preview_kind(self):
        return preview_kind_for(self.file.name)


@receiver(post_delete, sender=RopeRescueResource)
def delete_file_on_rope_rescue_resource_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


class Scorecard(models.Model):
    """A single MSHA competition scorecard, offered as a fillable PDF (for
    filling out on a device) and/or a non-fillable PDF (for printing)."""
    title = models.CharField(max_length=255, help_text="e.g. A Card - Map")
    fillable_file = models.FileField(upload_to='training/scorecards/', blank=True)
    non_fillable_file = models.FileField(upload_to='training/scorecards/', blank=True)
    sort_order = models.PositiveIntegerField(default=0, help_text="Scorecards are listed lowest number first")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.title

    @property
    def preview_file(self):
        """Prefer the non-fillable version for on-screen preview; fall back
        to the fillable one if that's all there is."""
        return self.non_fillable_file or self.fillable_file

    @property
    def preview_kind(self):
        f = self.preview_file
        return preview_kind_for(f.name) if f else ''


@receiver(post_delete, sender=Scorecard)
def delete_files_on_scorecard_delete(sender, instance, **kwargs):
    if instance.fillable_file:
        instance.fillable_file.delete(save=False)
    if instance.non_fillable_file:
        instance.non_fillable_file.delete(save=False)


class BenchingApparatus(models.Model):
    """A breathing apparatus teams bench, e.g. Draeger PSS BG4 plus. Groups
    the benching resources (manuals, IFUs, checklists) for that unit."""
    name = models.CharField(max_length=255, help_text="e.g. Draeger PSS BG4 plus")
    description = models.TextField(blank=True, help_text="Optional note shown above the unit's resource list")
    sort_order = models.PositiveIntegerField(default=0, help_text="Units are listed lowest number first")

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Benching apparatus'

    def __str__(self):
        return self.name


class BenchingResource(models.Model):
    """A document for benching a particular apparatus."""
    apparatus = models.ForeignKey(BenchingApparatus, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=255, help_text="e.g. PSS BG 4 / PSS BG 4 plus - Instructions for Use")
    description = models.TextField(blank=True, help_text="What this document covers")
    file = models.FileField(
        upload_to='training/benching/', blank=True,
        help_text="The document to preview/download. Leave blank for a link-only "
                  "resource (e.g. software hosted elsewhere) and set the source link below.",
    )
    source_url = models.URLField(
        blank=True,
        help_text="External link for this resource, e.g. the manufacturer's page or "
                  "hosted software. Shown as a link alongside (or instead of) the file.",
    )
    link_label = models.CharField(
        max_length=60, blank=True,
        help_text="Text for the source link, e.g. 'Access software'. Defaults to 'Source'.",
    )
    sort_order = models.PositiveIntegerField(default=0, help_text="Resources are listed lowest number first")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return f"{self.apparatus} - {self.title}"

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def preview_kind(self):
        return preview_kind_for(self.file.name)


@receiver(post_delete, sender=BenchingResource)
def delete_file_on_benching_resource_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


class Quiz(models.Model):
    """An interactive, auto-graded version of a written test — extracted
    from a ProblemDocument's question/answer PDF(s)."""
    problem = models.ForeignKey(CompetitionProblem, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255, help_text="e.g. First Aid Written Test")
    source_document = models.ForeignKey(
        ProblemDocument, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text="The original test PDF this quiz was extracted from (for the Take Test button).",
    )
    sort_order = models.PositiveIntegerField(default=0, help_text="Quizzes are listed lowest number first")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'title']
        verbose_name_plural = 'Quizzes'

    def __str__(self):
        return f"{self.problem} - {self.title}"

    def question_count(self):
        return self.questions.count()


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    image = models.FileField(
        upload_to='quiz_images/', blank=True,
        help_text="Diagram/figure shown with the question (e.g. a parts "
                  "illustration the question refers to).",
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.text[:60]


@receiver(post_delete, sender=QuizQuestion)
def delete_image_on_question_delete(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)


class QuizChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.text[:60]


@receiver(post_save, sender=CalendarEvent)
def link_competitions_on_event_save(sender, instance, **kwargs):
    """When calendar history is added, link any competition from that year that
    doesn't have a calendar entry yet and now matches one."""
    unlinked = Competition.objects.filter(
        calendar_event__isnull=True, year=instance.start_date.year
    )
    for competition in unlinked:
        match = competition.find_calendar_event()
        if match:
            competition.calendar_event = match
            competition.save(update_fields=['calendar_event'])
