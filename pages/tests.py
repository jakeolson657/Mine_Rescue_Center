from datetime import date, datetime, timezone
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from . import geo
from .search import search_events, state_name
from .calendar_export import (
    build_event_ics, google_calendar_url, outlook_calendar_url,
)
from .models import (
    CalendarEvent, Competition, CompetitionProblem, GeocodedLocation,
    SiteConfiguration, PROBLEM_CATEGORIES, categorize_problem,
)


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


class CalendarMapTests(TestCase):
    def _event(self, location, title='Test Contest'):
        return CalendarEvent.objects.create(
            title=title, start_date=date(2026, 9, 1), end_date=date(2026, 9, 2),
            location=location,
        )

    def _markers(self):
        return geo.map_markers(CalendarEvent.objects.all())

    def test_known_city_is_placed_exactly(self):
        self._event('Some Hall, 1 Main St, Morgantown, WV 26501')
        markers, unmapped = self._markers()
        self.assertEqual(unmapped, [])
        self.assertEqual(markers[0]['places'][0]['label'], 'Morgantown, WV')
        self.assertFalse(markers[0]['places'][0]['approximate'])

    def test_blank_location_is_left_off(self):
        self._event('')
        markers, unmapped = self._markers()
        self.assertEqual(markers, [])
        self.assertEqual(len(unmapped), 1)

    def test_unknown_city_uses_lookup_then_state_center(self):
        self._event('Civic Center, Newtown, WV')
        place = self._markers()[0][0]['places'][0]
        self.assertTrue(place['approximate'])
        GeocodedLocation.objects.create(query='Newtown, WV', latitude=38.0, longitude=-81.0)
        place = self._markers()[0][0]['places'][0]
        self.assertFalse(place['approximate'])

    def test_saving_event_looks_up_new_city(self):
        with mock.patch.object(geo, '_nominatim', return_value=(38.1, -81.2)) as lookup:
            with self.captureOnCommitCallbacks(execute=True):
                self._event('Civic Center, Newtown, WV')
            with self.captureOnCommitCallbacks(execute=True):
                self._event('Rec Center, Morgantown, WV')   # in the built-in table
        lookup.assert_called_once_with('Newtown, WV')
        self.assertTrue(GeocodedLocation.objects.filter(query='Newtown, WV').exists())

    def test_failed_lookup_does_not_break_save(self):
        with mock.patch.object(geo, '_nominatim', side_effect=OSError('offline')):
            with self.captureOnCommitCallbacks(execute=True):
                event = self._event('Civic Center, Newtown, WV')
        self.assertTrue(CalendarEvent.objects.filter(pk=event.pk).exists())
        self.assertFalse(GeocodedLocation.objects.exists())

    def test_surface_and_underground_colors(self):
        self._event('Elko, NV', title='Nevada Surface Mine Rescue Contest')
        self._event('Price, UT', title='Western Regional Mine Rescue Contest')
        response = self.client.get(reverse('calendar'), {'year': 2026, 'month': 9})
        self.assertContains(response, 'md-core md-surface')
        self.assertContains(response, 'md-core md-underground')
        self.assertContains(response, 'Competitions without a location are left off the map')


class CalendarSearchTests(TestCase):
    def setUp(self):
        def make(title, location, year):
            return CalendarEvent.objects.create(
                title=title, location=location,
                start_date=date(year, 6, 1), end_date=date(year, 6, 2))
        self.lex = make('KMI Mine Rescue Contest', 'Heritage Hall, Lexington, KY 40507', 2019)
        self.lex_old = make('KMI Mine Rescue Contest', 'Lexington, KY', 2015)
        self.nat = make('National Mine Rescue Contest', 'Sevierville, TN', 2018)
        self.wv = make('Fallen Heroes Contest', 'Logan, WV', 2020)
        self.va = make('Governors Cup', 'Abingdon, VA', 2021)

    def titles(self, query):
        return [e.pk for e in search_events(query)[0]]

    def test_matches_name_and_city(self):
        self.assertEqual(self.titles('kmi'), [self.lex.pk, self.lex_old.pk])  # newest first
        self.assertEqual(self.titles('sevierville'), [self.nat.pk])
        self.assertEqual(self.titles('fallen logan'), [self.wv.pk])

    def test_state_name_matches_abbreviation(self):
        self.assertEqual(set(self.titles('Kentucky')), {self.lex.pk, self.lex_old.pk})
        self.assertEqual(self.titles('west virginia'), [self.wv.pk])
        self.assertEqual(self.titles('virginia'), [self.va.pk])
        self.assertEqual(self.titles('WV'), [self.wv.pk])

    def test_lowercase_short_words_are_not_states(self):
        # "in" must not turn into Indiana.
        self.assertEqual(set(self.titles('contest in lexington')), {self.lex.pk, self.lex_old.pk})

    def test_year_matches_event_year(self):
        self.assertEqual(self.titles('2019 kmi'), [self.lex.pk])
        self.assertEqual(self.titles('kmi 2015'), [self.lex_old.pk])
        self.assertEqual(self.titles('2017 kmi'), [])

    def test_file_search_narrows_to_matching_files(self):
        from django.core.files.base import ContentFile
        from .models import ProblemDocument
        comp = Competition.objects.create(name='KMI', year=2019, calendar_event=self.lex)
        problem = CompetitionProblem.objects.create(competition=comp, title='Written Tests')
        for title in ('Team Trainer Written Test', 'Field Written Test'):
            doc = ProblemDocument(problem=problem, title=title)
            doc.file.save('t.pdf', ContentFile(b'%PDF-'), save=True)
            self.addCleanup(doc.file.delete, save=False)
        self.va.resources = [{'label': 'Final Results', 'url': 'https://example.com/r.pdf'}]
        self.va.save()

        results, _ = search_events('2019 trainer test')
        self.assertEqual([e.pk for e in results], [self.lex.pk])
        self.assertEqual([f['label'] for f in results[0].matched_files], ['Team Trainer Written Test'])

        results, _ = search_events('governors results')
        self.assertEqual([f['label'] for f in results[0].matched_files], ['Final Results'])

        # A contest-level match lists the event without picking out files.
        results, _ = search_events('2019 kmi')
        self.assertEqual(results[0].matched_files, [])

    def test_plural_matches_singular(self):
        self.assertEqual(self.titles('nationals'), [self.nat.pk])

    def test_matches_linked_competition_name(self):
        Competition.objects.create(name='Big Blue Classic', year=2021, calendar_event=self.va)
        self.assertEqual(self.titles('big blue'), [self.va.pk])

    def test_state_name_for_past_problems_search(self):
        self.assertEqual(state_name('Heritage Hall, Lexington, KY 40507'), 'Kentucky')
        self.assertEqual(state_name('Logan, WV'), 'West Virginia')
        self.assertEqual(state_name('Somewhere'), '')
        Competition.objects.create(name='KMI', year=2019, calendar_event=self.lex)
        response = self.client.get(reverse('past_problems'))
        self.assertContains(response, 'Lexington, KY 40507 Kentucky')

    def test_suggest_endpoint_and_full_results(self):
        response = self.client.get(reverse('calendar_search'), {'q': 'lexington'})
        self.assertContains(response, 'KMI Mine Rescue Contest', count=2)
        response = self.client.get(reverse('calendar_search'), {'q': 'nothing-here'})
        self.assertContains(response, 'No calendar events match')
        self.assertContains(response, reverse('past_problems') + '?q=nothing-here')
        response = self.client.get(reverse('calendar'), {'q': 'logan'})
        self.assertContains(response, '1 result for')
        self.assertContains(response, 'Fallen Heroes Contest')


class CategorizeProblemTests(TestCase):
    def test_event_types_match_on_title(self):
        self.assertEqual(categorize_problem("First Aid"), ['first-aid'])
        self.assertEqual(categorize_problem("Preshift"), ['preshift'])
        self.assertEqual(categorize_problem("Pre-Shift"), ['preshift'])
        self.assertEqual(categorize_problem("Bench"), ['bench'])
        self.assertEqual(categorize_problem("Written Exams"), ['written'])

    def test_team_technician_title_variants(self):
        # The archive files this contest under both word orders.
        self.assertEqual(categorize_problem("Tech Team"), ['team-technician'])
        self.assertEqual(categorize_problem("Technician Team"), ['team-technician'])
        self.assertEqual(categorize_problem("Team Technician"), ['team-technician'])
        # "Benchman" is the bench contest, not the team technician contest.
        self.assertEqual(categorize_problem("First Aid & Benchman Day 1"),
                         ['bench', 'first-aid'])

    def test_mine_type_matches_title_or_competition(self):
        self.assertEqual(categorize_problem("2024 Loveland COAL Day 1"), ['coal'])
        self.assertEqual(categorize_problem("2024 Loveland MNM Day 1"), ['mnm'])
        self.assertEqual(categorize_problem("Nonmetal"), ['mnm'])
        # The generic field problem inherits coal/MNM from the contest name...
        self.assertEqual(
            categorize_problem("Mine Rescue", "2022 National Coal Mine Rescue Contest"),
            ['coal'],
        )
        # ...but event-type words in the contest name do NOT bleed onto every
        # problem (First Aid here is only in the competition name).
        self.assertEqual(
            categorize_problem("Mine Rescue", "2022 Coal Mine Rescue and First Aid Contest"),
            ['coal'],
        )

    def test_generic_problem_has_no_category(self):
        self.assertEqual(
            categorize_problem("Mine Rescue", "2024 Colorado Mine Rescue Contest"), []
        )

    def test_multiple_categories_keep_display_order(self):
        self.assertEqual(categorize_problem("Coal Written Exam"), ['coal', 'written'])


class PastProblemsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # A contest with no mine type in its name: its First Aid problem is
        # tagged purely from the title, and the field problem stays untagged.
        cls.generic = Competition.objects.create(
            name="2024 Colorado Mine Rescue Contest", year=2024
        )
        CompetitionProblem.objects.create(competition=cls.generic, title="First Aid")
        CompetitionProblem.objects.create(competition=cls.generic, title="Mine Rescue")
        # A coal contest: its generic field problem inherits the coal tag.
        cls.coal = Competition.objects.create(
            name="2022 National Coal Mine Rescue Contest", year=2022
        )
        CompetitionProblem.objects.create(competition=cls.coal, title="Mine Rescue")

    def test_toolbar_and_chips_rendered(self):
        response = self.client.get(reverse('past_problems'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'repo-toolbar')
        self.assertContains(response, 'id="repo-search"')
        for slug, label in PROBLEM_CATEGORIES:
            self.assertContains(response, 'data-cat="%s"' % slug)
            self.assertContains(response, label)

    def test_problems_carry_category_data(self):
        response = self.client.get(reverse('past_problems'))
        # First Aid problem tagged from its title.
        self.assertContains(response, 'data-categories="first-aid"')
        # Generic "Mine Rescue" field problem tagged coal from the contest name.
        self.assertContains(response, 'data-categories="coal"')

    def test_competitions_carry_search_data(self):
        response = self.client.get(reverse('past_problems'))
        self.assertContains(response, 'data-search=')

    def test_documents_are_deferred_to_client(self):
        response = self.client.get(reverse('past_problems'))
        # Document rows are built client-side, not rendered server-side.
        self.assertNotContains(response, '<div class="document-item">')
        # Each problem ships a lazy-load container plus a JSON data bundle.
        self.assertContains(response, 'data-docs="docs-')
        self.assertContains(response, 'type="application/json"')
