from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pages.geo import NORTH_AMERICA_HEIGHT, NORTH_AMERICA_WIDTH, project_north_america

from . import notify
from .models import ForumProfile, Status, TeamListing
from .views import _combine_crowded_pins

User = get_user_model()
URL = reverse('forum:team_listing')
VALID = {
    'name': 'Raleigh Blue', 'company': 'Example Coal', 'team_type': 'professional', 'city': 'Beckley',
    'state': 'WV', 'sector': 'coal', 'contact_email': '', 'contact_phone': '', 'consent': 'on',
}


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TeamMapTests(TestCase):
    def member(self, email='a@example.com', name='Alpha Member', **profile):
        user = User.objects.create(username=email, email=email, date_joined=timezone.now() - timedelta(days=5))
        ForumProfile.objects.create(user=user, display_name=name, **profile)
        self.client.force_login(user)
        return user

    def listing(self, user, status=Status.VISIBLE, **fields):
        data = {
            'name': 'Raleigh Blue', 'company': 'Example Coal', 'team_type': 'professional',
            'city': 'Beckley', 'state': 'WV', 'sector': 'coal', **fields,
        }
        return TeamListing.objects.create(member=user, status=status, **data)

    def index(self):
        return self.client.get(reverse('forum:index'))

    def test_signing_in_is_required(self):
        response = self.client.get(URL)
        self.assertTrue(response.url.startswith(reverse('forum:signin')))

    def test_signed_in_account_without_a_display_name_goes_straight_to_the_form(self):
        user = User.objects.create(username='new@example.com', email='new@example.com')
        self.client.force_login(user)
        self.assertContains(self.client.get(URL), 'Add your team to the map')
        self.client.post(URL, VALID)
        self.assertEqual(TeamListing.objects.get().member, user)
        self.assertEqual(len(mail.outbox), 1)

    def test_form_starts_from_the_members_profile(self):
        self.member(team='Raleigh Blue', state='WV', district='coal')
        response = self.client.get(URL)
        self.assertContains(response, 'value="Raleigh Blue"')
        self.assertEqual(response.context['form'].initial['state'], 'WV')

    def test_new_team_waits_for_approval(self):
        self.member()
        self.client.post(URL, VALID)
        listing = TeamListing.objects.get()
        self.assertEqual(listing.status, Status.PENDING)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Raleigh Blue', mail.outbox[0].body)
        self.assertNotContains(self.index(), 'Raleigh Blue')

    def test_consent_is_required(self):
        self.member()
        response = self.client.post(URL, {**VALID, 'consent': ''})
        self.assertContains(response, 'Please confirm')
        self.assertFalse(TeamListing.objects.exists())

    def test_approved_team_appears_without_member_details(self):
        user = self.member(email='private@example.com', name='Private Person')
        listing = self.listing(user, status=Status.PENDING, company='Example Coal')
        request = RequestFactory().get('/')
        self.assertTrue(notify.approve_team_and_notify(request, listing))
        self.assertEqual(mail.outbox[0].to, ['private@example.com'])

        self.client.logout()
        response = self.index()
        self.assertContains(response, 'Raleigh Blue')
        self.assertContains(response, 'Beckley, WV')
        self.assertContains(response, 'class="fm-pin professional"')
        self.assertNotContains(response, 'private@example.com')
        self.assertNotContains(response, 'Private Person')

    def test_nearby_teams_share_one_pin(self):
        self.listing(self.member())
        self.listing(self.member('b@example.com', 'Beta Member'), name='Beaver Red', city='Beaver')
        response = self.index()
        self.assertEqual(len(response.context['team_markers']), 1)
        self.assertEqual(response.context['team_markers'][0]['count'], 2)
        self.assertEqual(len(response.context['team_rows']), 2)

    def test_towns_with_room_keep_their_own_pins_on_the_full_map(self):
        self.listing(self.member())
        self.listing(self.member('b@example.com', 'Beta Member'), name='Morgantown Black', city='Morgantown')
        self.listing(self.member('c@example.com', 'Gamma Member'), name='Elko Gold', city='Elko', state='NV')
        labels = {m['label'] for m in self.index().context['team_markers']}
        self.assertEqual(labels, {'Beckley, WV', 'Morgantown, WV', 'Elko, NV'})

    def test_map_shows_north_america_with_alaska_in_its_true_place(self):
        self.listing(self.member(), name='Fairbanks Gold', city='Fairbanks', state='AK')
        self.listing(self.member('b@example.com', 'Beta Member'), name='Elko Green', city='Elko', state='NV')
        response = self.index()
        pins = {m['label']: m for m in response.context['team_markers']}
        self.assertLess(pins['Fairbanks, AK']['y'], pins['Elko, NV']['y'])
        self.assertLess(pins['Fairbanks, AK']['x'], pins['Elko, NV']['x'])
        self.assertContains(response, 'viewBox="0 0 975 910"')
        self.assertContains(response, 'class="fm-neighbor"', count=2)
        self.assertContains(response, '<path data-state=', count=50)
        self.assertNotContains(response, 'data-state="Hawaii"')

    def test_hawaii_cannot_be_chosen_for_a_team(self):
        self.member()
        self.assertNotContains(self.client.get(URL), 'value="HI"')
        self.client.post(URL, {**VALID, 'city': 'Hilo', 'state': 'HI'})
        self.assertFalse(TeamListing.objects.exists())

    def test_recent_activity_button_sits_between_categories_and_the_map(self):
        html = self.index().content.decode()
        button = html.index('href="#recent-activity"')
        self.assertLess(html.index('class="fm-cats"'), button)
        self.assertLess(button, html.index('id="teams"'))
        self.assertLess(html.index('id="teams"'), html.index('id="recent-activity"'))

    def test_heading_comes_before_the_team_count(self):
        html = self.index().content.decode()
        self.assertLess(html.index('id="fm-teams-title"'), html.index('class="fm-teams-kicker"'))

    def test_every_pin_fits_inside_the_map(self):
        for lat, lng in [(71.3, -156.8), (24.6, -81.8), (44.9, -67.0), (48.4, -124.7)]:
            x, y = project_north_america(lat, lng)
            self.assertTrue(0 <= x <= NORTH_AMERICA_WIDTH and 0 <= y <= NORTH_AMERICA_HEIGHT, (lat, lng, x, y))

    def test_teams_in_one_town_show_their_count_on_a_larger_pin(self):
        self.listing(self.member())
        self.listing(self.member('b@example.com', 'Beta Member'), name='Raleigh Red')
        self.listing(self.member('c@example.com', 'Gamma Member'), name='Elko Green', city='Elko', state='NV')
        pins = {m['label']: (m['count'], m['radius']) for m in self.index().context['team_markers']}
        self.assertEqual(pins, {'Beckley, WV': (2, 10), 'Elko, NV': (1, 6)})

    def test_a_combined_pin_keeps_every_town_and_sits_between_them(self):
        self.listing(self.member())
        self.listing(self.member('b@example.com', 'Beta Member'), name='Beaver Red', city='Beaver')
        response = self.index()
        marker = response.context['team_markers'][0]
        xs = sorted(t['x'] for t in response.context['team_towns'])
        self.assertEqual({p['label'] for p in marker['places']}, {'Beckley, WV', 'Beaver, WV'})
        self.assertTrue(xs[0] <= marker['x'] <= xs[1])

    def test_combining_does_not_depend_on_the_order_teams_were_added(self):
        def pin(x, label):
            return {'x': x, 'y': 100.0, 'count': 1, 'places': [{'label': label}]}

        forward = _combine_crowded_pins([pin(100.0, 'A'), pin(107.0, 'B'), pin(130.0, 'C')])
        backward = _combine_crowded_pins([pin(130.0, 'C'), pin(107.0, 'B'), pin(100.0, 'A')])
        self.assertEqual(sorted(p['x'] for p in forward), sorted(p['x'] for p in backward))
        self.assertEqual(sorted(p['x'] for p in forward), [103.5, 130.0])

    def test_teams_sharing_a_pin_get_their_own_town_pins_in_the_state_view(self):
        self.listing(self.member())
        self.listing(self.member('b@example.com', 'Beta Member'), name='Beaver Red', city='Beaver', team_type='volunteer')
        response = self.index()
        towns = {t['label']: t for t in response.context['team_towns']}
        self.assertEqual(set(towns), {'Beckley, WV', 'Beaver, WV'})
        self.assertEqual(towns['Beaver, WV']['kind'], 'volunteer')
        self.assertEqual(towns['Beaver, WV']['state'], 'West Virginia')
        self.assertNotEqual(towns['Beckley, WV']['x'], towns['Beaver, WV']['x'])
        self.assertContains(response, '>Beaver</text>')

    def test_teams_in_one_town_share_a_town_pin(self):
        self.listing(self.member())
        self.listing(self.member('b@example.com', 'Beta Member'), name='Raleigh Red')
        towns = self.index().context['team_towns']
        self.assertEqual([(t['label'], t['count']) for t in towns], [('Beckley, WV', 2)])

    def test_list_rows_name_their_town_and_state(self):
        self.listing(self.member())
        row = self.index().context['team_rows'][0]
        self.assertEqual((row['town'], row['state']), (1, 'West Virginia'))

    def test_pin_across_a_border_opens_the_state_with_the_most_teams(self):
        self.listing(self.member(), city='Bluefield')
        self.listing(self.member('b@example.com', 'Beta Member'), name='Bluefield Red', city='Bluefield')
        self.listing(self.member('c@example.com', 'Gamma Member'), name='Cedar Gold', city='Cedar Bluff', state='VA')
        marker = self.index().context['team_markers'][0]
        self.assertEqual((marker['count'], marker['state']), (3, 'West Virginia'))

    def test_state_zoom_is_available_before_any_team_is_listed(self):
        response = self.index()
        self.assertContains(response, 'id="fm-map-back"')
        self.assertContains(response, 'openStateView')

    def test_editing_an_approved_team_sends_it_back_for_review(self):
        self.listing(self.member())
        self.client.post(URL, {**VALID, 'name': 'Something Else'})
        listing = TeamListing.objects.get()
        self.assertEqual((listing.name, listing.status), ('Something Else', Status.PENDING))
        self.assertNotContains(self.index(), 'Something Else')

    def test_saving_without_changes_keeps_the_team_on_the_map(self):
        self.listing(self.member(), company='Example Coal')
        self.client.post(URL, VALID)
        self.assertEqual(TeamListing.objects.get().status, Status.VISIBLE)
        self.assertEqual(mail.outbox, [])

    def test_member_can_remove_their_team(self):
        self.listing(self.member())
        self.client.post(reverse('forum:remove_team_listing'))
        self.assertFalse(TeamListing.objects.exists())

    def test_removing_only_affects_your_own_team(self):
        self.listing(self.member())
        self.member('b@example.com', 'Beta Member')
        self.client.post(reverse('forum:remove_team_listing'))
        self.assertEqual(TeamListing.objects.count(), 1)

    def test_declined_team_cannot_be_resubmitted_by_editing(self):
        self.listing(self.member(), status=Status.HIDDEN)
        self.client.post(URL, {**VALID, 'name': 'Try Again'})
        listing = TeamListing.objects.get()
        self.assertEqual((listing.name, listing.status), ('Raleigh Blue', Status.HIDDEN))

    def test_duplicate_team_in_a_state_is_rejected(self):
        self.listing(self.member())
        self.member('b@example.com', 'Beta Member')
        response = self.client.post(URL, {**VALID, 'name': 'raleigh blue'})
        self.assertContains(response, 'already listed')
        self.assertEqual(TeamListing.objects.count(), 1)

    def test_links_and_bad_towns_are_rejected(self):
        self.member()
        for field, value in [('name', 'www.spam.example'), ('company', 'https://spam.example'), ('city', 'Beckley, WV'), ('city', '12345')]:
            response = self.client.post(URL, {**VALID, field: value})
            self.assertEqual(response.status_code, 200, (field, value))
            self.assertFalse(TeamListing.objects.exists(), (field, value))

    def test_town_names_with_punctuation_are_allowed(self):
        self.member()
        self.client.post(URL, {**VALID, 'city': "St. John's-Oak Hill"})
        self.assertEqual(TeamListing.objects.get().city, "St. John's-Oak Hill")

    def test_team_type_decides_what_organization_is_required(self):
        self.member()
        self.assertContains(self.client.post(URL, {**VALID, 'team_type': ''}), 'choose a team type')
        self.assertContains(self.client.post(URL, {**VALID, 'company': ''}), 'team&#x27;s company.')
        self.assertContains(self.client.post(URL, {**VALID, 'team_type': 'collegiate', 'company': ''}), 'team&#x27;s college.')
        self.assertFalse(TeamListing.objects.exists())

    def test_collegiate_team_is_saved_with_its_college(self):
        self.member()
        self.client.post(URL, {**VALID, 'team_type': 'collegiate', 'company': 'Example University'})
        self.assertEqual(TeamListing.objects.get().company, 'Example University')

    def test_volunteer_team_needs_no_company_and_drops_any_left_behind(self):
        self.member()
        self.client.post(URL, {**VALID, 'team_type': 'volunteer', 'company': 'https://left.behind.example'})
        listing = TeamListing.objects.get()
        self.assertEqual((listing.team_type, listing.company), ('volunteer', ''))

    def test_team_contact_is_only_shown_to_signed_in_members(self):
        self.member()
        self.client.post(URL, {**VALID, 'contact_email': 'team@example.com', 'contact_phone': '1-304-555-0100'})
        listing = TeamListing.objects.get()
        self.assertEqual(listing.contact_phone, '(304) 555-0100')
        self.assertNotContains(self.index(), 'team@example.com')
        listing.approve()

        response = self.index()
        self.assertContains(response, 'href="mailto:team@example.com"')
        self.assertContains(response, 'href="tel:+13045550100"')
        self.assertContains(response, 'only visible to signed-in members')

        self.client.logout()
        response = self.index()
        self.assertContains(response, 'Raleigh Blue')
        self.assertNotContains(response, 'team@example.com')
        self.assertNotContains(response, '555-0100')
        self.assertContains(response, 'only visible to signed-in members')
        self.assertContains(response, 'Sign in</a> to see them')

    def test_bad_team_contact_is_rejected(self):
        self.member()
        self.assertContains(self.client.post(URL, {**VALID, 'contact_email': 'not-an-email'}), 'valid email')
        self.assertContains(self.client.post(URL, {**VALID, 'contact_phone': '555-0100'}), '10-digit')
        self.assertFalse(TeamListing.objects.exists())

    def test_pin_color_follows_team_type(self):
        self.listing(self.member(), team_type='collegiate')
        self.listing(self.member('b@example.com', 'Beta Member'), name='Elko Green', city='Elko', state='NV', team_type='volunteer')
        kinds = {m['label']: m['kind'] for m in self.index().context['team_markers']}
        self.assertEqual(kinds, {'Beckley, WV': 'collegiate', 'Elko, NV': 'volunteer'})

    def test_different_types_sharing_a_pin_are_marked_mixed(self):
        self.listing(self.member(), team_type='collegiate')
        self.listing(self.member('b@example.com', 'Beta Member'), name='Beaver Red', city='Beaver', team_type='volunteer')
        response = self.index()
        self.assertEqual(response.context['team_markers'][0]['kind'], 'mixed')
        self.assertContains(response, 'Multiple types')

    def test_banned_member_cannot_list_a_team(self):
        self.member(banned=True)
        self.client.post(URL, VALID)
        self.assertFalse(TeamListing.objects.exists())
