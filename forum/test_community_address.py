from django.test import TestCase
from django.urls import reverse


class CommunityAddressTests(TestCase):
    def test_pages_live_at_the_community_address(self):
        self.assertEqual(reverse('forum:index'), '/community/')
        self.assertEqual(reverse('forum:team_listing'), '/community/teams/yours/')
        self.assertEqual(self.client.get('/community/').status_code, 200)

    def test_old_home_address_forwards_permanently(self):
        response = self.client.get('/forum/')
        self.assertEqual((response.status_code, response['Location']), (301, '/community/'))

    def test_old_address_without_a_slash_reaches_the_community(self):
        response = self.client.get('/forum', follow=True)
        self.assertEqual(response.redirect_chain[-1][0], '/community/')
        self.assertEqual(response.status_code, 200)

    def test_old_links_keep_their_path_and_query(self):
        response = self.client.get('/forum/signin/confirm/?t=abc%3Adef&x=1')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/community/signin/confirm/?t=abc%3Adef&x=1')

    def test_forms_left_open_on_old_pages_keep_their_submission(self):
        response = self.client.post('/forum/signin/', {'email': 'a@example.com'})
        self.assertEqual((response.status_code, response['Location']), (308, '/community/signin/'))

    def test_old_address_cannot_forward_to_another_site(self):
        response = self.client.get('/forum//evil.example/')
        self.assertEqual(response['Location'], '/community//evil.example/')
