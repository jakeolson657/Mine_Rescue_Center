from datetime import date, datetime, timezone

from django.test import TestCase
from django.urls import reverse

from .calendar_export import (
    build_event_ics, google_calendar_url, outlook_calendar_url,
)
from .models import CalendarEvent, SiteConfiguration


class CalendarExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = CalendarEvent.objects.create(
            title="Loveland, Colorado Contest",
            start_date=date(2026, 6, 16),
            end_date=date(2026, 6, 18),
            location="Loveland, CO",
            description="Coal & nonmetal; bring SCBA.",
        )
        cls.one_day = CalendarEvent.objects.create(
            title="Bench Contest",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
            location="Denver, CO",
        )

    def test_ics_is_well_formed_all_day_event(self):
        ics = build_event_ics(
            self.event, now=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        )
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertIn("\r\nEND:VCALENDAR\r\n", ics)
        self.assertIn("DTSTART;VALUE=DATE:20260616", ics)
        # DTEND is exclusive -> day after the last day (the 18th -> the 19th).
        self.assertIn("DTEND;VALUE=DATE:20260619", ics)
        self.assertIn("SUMMARY:Loveland\\, Colorado Contest", ics)
        self.assertIn("LOCATION:Loveland\\, CO", ics)
        self.assertIn("DTSTAMP:20260102T030405Z", ics)
        self.assertIn("UID:event-{}@minerescuecenter.com".format(self.event.pk), ics)
        # Every line must use CRLF endings.
        self.assertNotIn("\n", ics.replace("\r\n", ""))

    def test_ics_single_day_end_is_next_day(self):
        ics = build_event_ics(self.one_day)
        self.assertIn("DTSTART;VALUE=DATE:20260701", ics)
        self.assertIn("DTEND;VALUE=DATE:20260702", ics)

    def test_ics_escapes_special_characters(self):
        event = CalendarEvent.objects.create(
            title="A; B, C",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
            location="X",
            description="line one\nline two",
        )
        ics = build_event_ics(event)
        self.assertIn("SUMMARY:A\\; B\\, C", ics)
        self.assertIn("line one\\nline two", ics)

    def test_google_link_uses_exclusive_end(self):
        url = google_calendar_url(self.event)
        self.assertIn("calendar.google.com/calendar/render", url)
        self.assertIn("action=TEMPLATE", url)
        self.assertIn("dates=20260616%2F20260619", url)  # 16th .. 19th exclusive
        self.assertIn("Loveland", url)

    def test_outlook_link_is_all_day(self):
        url = outlook_calendar_url(self.event)
        self.assertIn("outlook.live.com/calendar", url)
        self.assertIn("allday=true", url)
        self.assertIn("startdt=2026-06-16", url)
        self.assertIn("enddt=2026-06-19", url)

    def test_event_ics_endpoint_downloads_file(self):
        response = self.client.get(reverse('event_ics', args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'], 'text/calendar; charset=utf-8'
        )
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.ics', response['Content-Disposition'])
        body = response.content.decode('utf-8')
        self.assertIn('BEGIN:VEVENT', body)
        # The downloaded file links back to the event's absolute URL.
        self.assertIn('URL:http', body)

    def test_event_ics_endpoint_404_for_missing_event(self):
        response = self.client.get(reverse('event_ics', args=[999999]))
        self.assertEqual(response.status_code, 404)


class CalendarPageTests(TestCase):
    def test_calendar_page_has_picker(self):
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cal-picker-toggle')
        self.assertContains(response, 'data-today-year')

    def test_msha_link_shown_when_configured(self):
        config = SiteConfiguration.load()
        config.msha_calendar_url = 'https://example.com/msha-2027'
        config.save()
        response = self.client.get(reverse('calendar'))
        self.assertContains(response, 'https://example.com/msha-2027')
        self.assertContains(response, 'Official MSHA Contest Calendar')

    def test_msha_link_hidden_when_blank(self):
        config = SiteConfiguration.load()
        config.msha_calendar_url = ''
        config.save()
        response = self.client.get(reverse('calendar'))
        # The <a> is gone (the .msha-link CSS rules still exist in the <style>).
        self.assertNotContains(response, 'class="msha-link"')
        self.assertNotContains(response, 'Official MSHA Contest Calendar')

    def test_site_configuration_is_singleton(self):
        first = SiteConfiguration.load()
        first.msha_calendar_url = 'https://a.test'
        first.save()
        again = SiteConfiguration.load()
        again.msha_calendar_url = 'https://b.test'
        again.save()
        self.assertEqual(SiteConfiguration.objects.count(), 1)
        self.assertEqual(SiteConfiguration.load().pk, 1)
        self.assertEqual(SiteConfiguration.load().msha_calendar_url, 'https://b.test')

    def test_event_detail_has_export_buttons(self):
        event = CalendarEvent.objects.create(
            title="Test Contest",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            location="Somewhere",
        )
        response = self.client.get(reverse('event_detail', args=[event.pk]))
        self.assertContains(response, 'calendar.google.com')
        self.assertContains(response, 'outlook.live.com')
        self.assertContains(response, reverse('event_ics', args=[event.pk]))
