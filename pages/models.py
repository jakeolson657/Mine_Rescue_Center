import os

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class CalendarEvent(models.Model):
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    contact_info = models.TextField(blank=True)
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


class PastProblem(models.Model):
    title = models.CharField(max_length=200)
    competition = models.CharField(
        max_length=200, blank=True,
        help_text="Which competition this problem is from, e.g. 2025 Kentucky Mining Institute Contest"
    )
    year = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='problems/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', 'title']

    def __str__(self):
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)


@receiver(post_delete, sender=PastProblem)
def delete_file_on_problem_delete(sender, instance, **kwargs):
    # FileField doesn't remove files from disk on row deletion
    if instance.file:
        instance.file.delete(save=False)
