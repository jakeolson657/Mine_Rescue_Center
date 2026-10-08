from django.core.management.base import BaseCommand

from pages.geo import geocode_location, locate
from pages.models import CalendarEvent


class Command(BaseCommand):
    help = ("Look up map coordinates for calendar event cities that aren't in "
            "the built-in table yet (normally done automatically on save).")

    def handle(self, *args, **options):
        locations = set(CalendarEvent.objects.values_list('location', flat=True))
        added = 0
        for location in sorted(locations):
            place = geocode_location(location)
            if place:
                added += 1
                self.stdout.write(f"  {place.query}: {place.latitude:.3f}, {place.longitude:.3f}")
        missing = sorted({loc for loc in locations
                          if (found := locate(loc)) is None or found[2]})
        self.stdout.write(self.style.SUCCESS(f"Added {added} location(s)."))
        for loc in missing:
            self.stdout.write(f"  not placed exactly: {loc!r}")
