from django.db import models
from datetime import timedelta


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

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1
