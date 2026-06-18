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
        """'image', 'frame' (PDF/text rendered in an iframe), or '' when the
        browser can't display the file type inline."""
        ext = os.path.splitext(self.file.name)[1].lower()
        if ext in PREVIEW_IMAGE_EXTENSIONS:
            return 'image'
        if ext in PREVIEW_FRAME_EXTENSIONS:
            return 'frame'
        return ''


@receiver(post_delete, sender=ProblemDocument)
def delete_file_on_document_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


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
