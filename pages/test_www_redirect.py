from django.test import TestCase, override_settings

WWW = 'www.minerescuecenter.com'
MAIN = 'minerescuecenter.com'


@override_settings(ALLOWED_HOSTS=[MAIN, WWW])
class WwwRedirectTests(TestCase):
    def test_www_home_forwards_to_the_main_address(self):
        response = self.client.get('/', headers={'host': WWW})
        self.assertEqual((response.status_code, response['Location']), (301, f'http://{MAIN}/'))

    def test_path_and_query_are_kept(self):
        response = self.client.get('/community/search/?q=rules&page=2', headers={'host': WWW})
        self.assertEqual(response['Location'], f'http://{MAIN}/community/search/?q=rules&page=2')

    def test_secure_visits_stay_secure(self):
        response = self.client.get('/community/', headers={'host': WWW}, secure=True)
        self.assertEqual(response['Location'], f'https://{MAIN}/community/')

    def test_uppercase_www_is_redirected(self):
        response = self.client.get('/', headers={'host': WWW.upper()})
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'].lower(), f'http://{MAIN}/')

    def test_form_submissions_keep_their_data(self):
        response = self.client.post('/community/signin/', {'email': 'a@example.com'}, headers={'host': WWW})
        self.assertEqual((response.status_code, response['Location']), (308, f'http://{MAIN}/community/signin/'))

    def test_main_address_is_served_normally(self):
        self.assertEqual(self.client.get('/', headers={'host': MAIN}).status_code, 200)

    def test_unknown_www_host_is_rejected(self):
        self.assertEqual(self.client.get('/', headers={'host': 'www.evil.example'}).status_code, 400)
