import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pages.models import CalendarEvent, Competition, CompetitionProblem

from .models import Category, ForumProfile, Post, Report, Status, Subscription, Thread

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ForumTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = Category.objects.get(slug='rules')

    def member(self, email='a@example.com', name='Alpha', trusted=True, days_old=5):
        user = User.objects.create(username=email, email=email, date_joined=timezone.now() - timedelta(days=days_old))
        ForumProfile.objects.create(user=user, display_name=name, trusted=trusted)
        self.client.force_login(user)
        return user

    def start_thread(self, **extra):
        data = {'category': self.cat.pk, 'title': 'Rule 14 question', 'body': 'How does it apply?', **extra}
        return self.client.post(reverse('forum:new_thread'), data)

    # ---- sign-in ----

    def test_email_link_signs_in_once_then_asks_for_profile(self):
        self.client.post(reverse('forum:signin'), {'email': 'New@Example.com'})
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r'https?://\S+', mail.outbox[0].body).group(0)
        path = link.split('testserver', 1)[1]

        # Opening the link alone doesn't sign in (mail scanners pre-open links).
        self.assertContains(self.client.get(path), 'new@example.com')
        self.assertNotIn('_auth_user_id', self.client.session)

        token = re.search(r't=([^&\s]+)', link).group(1)
        from urllib.parse import unquote
        resp = self.client.post(reverse('forum:signin_confirm'), {'t': unquote(token)})
        self.assertTrue(resp.url.startswith(reverse('forum:profile')))
        self.assertEqual(User.objects.get().email, 'new@example.com')

        # Second use fails.
        self.client.logout()
        resp = self.client.post(reverse('forum:signin_confirm'), {'t': unquote(token)})
        self.assertEqual(resp.status_code, 400)

    def test_remember_device_keeps_session_after_browser_closes(self):
        from . import signin as signin_mod
        for remember, browser_close in [('1', False), ('', True)]:
            self.client.logout()
            token = signin_mod.make_token('r@example.com', '/forum/')
            self.client.post(reverse('forum:signin_confirm'), {'t': token, 'remember': remember})
            self.assertIn('_auth_user_id', self.client.session)
            self.assertEqual(self.client.session.get_expire_at_browser_close(), browser_close)
            if remember:
                self.assertGreater(self.client.session.get_expiry_age(), 300 * 24 * 3600)

    def test_profile_requires_a_known_state(self):
        user = User.objects.create(username='s@example.com', email='s@example.com')
        self.client.force_login(user)
        data = {'display_name': 'Sam Example', 'state': 'Atlantis', 'email_on_reply': 'on'}
        self.assertContains(self.client.post(reverse('forum:profile'), data), 'pick your state')
        for typed in ['west virginia', 'WV', ' West  Virginia ']:
            self.client.post(reverse('forum:profile'), {**data, 'state': typed})
            self.assertEqual(ForumProfile.objects.get(user=user).state, 'WV')
        self.assertContains(self.client.get(reverse('forum:profile')), 'value="West Virginia"')
        self.assertContains(self.client.post(reverse('forum:profile'), {**data, 'state': ''}), 'Please enter your state')

    def test_site_account_can_skip_state(self):
        user = User.objects.create(username='info', email='Info@MineRescueCenter.com')
        self.client.force_login(user)
        self.client.post(reverse('forum:profile'), {'display_name': 'Mine Rescue Center', 'state': '', 'email_on_reply': 'on'})
        self.assertEqual(ForumProfile.objects.get(user=user).display_name, 'Mine Rescue Center')

    def test_posting_requires_display_name(self):
        user = User.objects.create(username='b@example.com', email='b@example.com')
        self.client.force_login(user)
        resp = self.client.get(reverse('forum:new_thread'))
        self.assertTrue(resp.url.startswith(reverse('forum:profile')))

    # ---- moderation ----

    def test_new_member_posts_are_queued_until_approved_then_trusted(self):
        user = self.member(trusted=False)
        self.start_thread()
        thread = Thread.objects.get()
        self.assertEqual(thread.status, Status.PENDING)
        self.assertEqual(len(mail.outbox), 1)  # moderator notified

        # Author sees it; the public doesn't.
        self.assertEqual(self.client.get(thread.get_absolute_url()).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(thread.get_absolute_url()).status_code, 404)

        thread.posts.get().approve()
        thread.refresh_from_db()
        self.assertEqual(thread.status, Status.VISIBLE)
        self.assertEqual(self.client.get(thread.get_absolute_url()).status_code, 200)

        self.client.force_login(user)
        self.client.post(reverse('forum:reply', args=[thread.pk]), {'body': 'Second post'})
        Post.objects.get(body='Second post').approve()
        self.assertTrue(ForumProfile.objects.get(user=user).trusted)

    def test_reply_notifies_followers(self):
        self.member('a@example.com', 'Alpha')
        self.start_thread()
        thread = Thread.objects.get()
        self.member('b@example.com', 'Bravo')
        self.client.post(reverse('forum:reply', args=[thread.pk]), {'body': 'Here is how'})
        self.assertEqual([m.to for m in mail.outbox], [['a@example.com']])
        thread.refresh_from_db()
        self.assertEqual(thread.reply_count, 1)
        self.assertEqual(Subscription.objects.filter(thread=thread).count(), 2)

    def test_three_reports_hide_a_post(self):
        self.member('a@example.com', 'Alpha')
        self.start_thread()
        thread = Thread.objects.get()
        for i in range(3):
            self.member(f'r{i}@example.com', f'Reporter {i}')
            self.client.post(reverse('forum:report_post', args=[thread.posts.get().pk]), {'reason': 'spam'})
        self.assertEqual(Report.objects.count(), 3)
        thread.refresh_from_db()
        self.assertEqual(thread.status, Status.HIDDEN)

    def test_new_accounts_cannot_post_links(self):
        self.member(trusted=False, days_old=0)
        resp = self.start_thread(body='Buy now at https://spam.example')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Thread.objects.exists())

    def test_daily_thread_limit(self):
        self.member()
        for i in range(5):
            self.start_thread(title=f'Question number {i}')
        resp = self.start_thread(title='One too many')
        self.assertContains(resp, 'up to 5 threads a day')
        self.assertEqual(Thread.objects.count(), 5)

    def test_edit_by_probation_member_requeues(self):
        user = self.member(trusted=False)
        self.start_thread()
        post = Post.objects.get()
        post.approve()
        ForumProfile.objects.filter(user=user).update(trusted=False)
        self.client.post(reverse('forum:edit_post', args=[post.pk]), {'body': 'Changed text'})
        post.refresh_from_db()
        self.assertEqual(post.status, Status.PENDING)

    # ---- archive links ----

    def test_problem_threads_wait_until_contest_is_held(self):
        self.member()
        event = CalendarEvent.objects.create(
            title='Future contest', location='Beckley, WV',
            start_date=timezone.localdate() + timedelta(days=30),
            end_date=timezone.localdate() + timedelta(days=31),
        )
        comp = Competition.objects.create(name='Future contest', year=2099, calendar_event=event)
        problem = CompetitionProblem.objects.create(competition=comp, title='Coal Day 1')
        resp = self.start_thread(problem=problem.pk)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Thread.objects.exists())

        event.start_date = event.end_date = timezone.localdate() - timedelta(days=1)
        event.save()
        self.start_thread(problem=problem.pk)
        self.assertEqual(Thread.objects.get().problem, problem)
        resp = self.client.get(reverse('forum:about', args=['problem', problem.pk]))
        self.assertContains(resp, 'Rule 14 question')

    def test_accepted_answer(self):
        self.member('a@example.com', 'Alpha')
        self.start_thread()
        thread = Thread.objects.get()
        author = User.objects.get(email='a@example.com')
        self.member('b@example.com', 'Bravo')
        self.client.post(reverse('forum:reply', args=[thread.pk]), {'body': 'The answer'})
        answer = Post.objects.get(body='The answer')
        # Only the thread author (or staff) may mark it.
        self.assertEqual(self.client.post(reverse('forum:mark_answer', args=[answer.pk])).status_code, 404)
        self.client.force_login(author)
        self.client.post(reverse('forum:mark_answer', args=[answer.pk]))
        answer.refresh_from_db()
        self.assertTrue(answer.is_answer)
        self.assertContains(self.client.get(thread.get_absolute_url()), 'accepted answer')

    def test_only_the_site_account_moderates(self):
        self.member('a@example.com', 'Alpha', trusted=False)
        self.start_thread()
        post = Post.objects.get()
        admin = self.member('admin@example.com', 'Site Admin')
        User.objects.filter(pk=admin.pk).update(is_staff=True, is_superuser=True)
        moderate = reverse('forum:moderate', args=[post.pk])
        self.assertEqual(self.client.post(moderate, {'action': 'approve'}).status_code, 404)
        self.assertEqual(self.client.get(reverse('forum:edit_post', args=[post.pk])).status_code, 404)

        mod = self.member('info@minerescuecenter.com', 'Mine Rescue Center')
        self.assertTrue(mod.forum_profile.is_moderator)
        self.assertContains(self.client.get(post.thread.get_absolute_url()), '>Approve<')
        self.client.post(moderate, {'action': 'approve'})
        post.refresh_from_db()
        self.assertEqual(post.status, Status.VISIBLE)

    def test_moderator_deletes_posts_and_threads(self):
        self.member('a@example.com', 'Alpha')
        self.start_thread()
        thread = Thread.objects.get()
        self.client.post(reverse('forum:reply', args=[thread.pk]), {'body': 'A reply'})
        reply = Post.objects.get(body='A reply')
        opening = thread.posts.order_by('created_at').first()

        # Members (even the author) can't delete.
        self.client.post(reverse('forum:moderate', args=[reply.pk]), {'action': 'delete'})
        self.assertTrue(Post.objects.filter(pk=reply.pk).exists())

        self.member('info@minerescuecenter.com', 'Mine Rescue Center')
        self.assertContains(self.client.get(thread.get_absolute_url()), 'Delete thread')
        self.client.post(reverse('forum:moderate', args=[reply.pk]), {'action': 'delete'})
        self.assertFalse(Post.objects.filter(pk=reply.pk).exists())
        thread.refresh_from_db()
        self.assertEqual(thread.reply_count, 0)

        resp = self.client.post(reverse('forum:moderate', args=[opening.pk]), {'action': 'delete'})
        self.assertEqual(resp.url, self.cat.get_absolute_url())
        self.assertFalse(Thread.objects.exists())

    def test_pages_render(self):
        self.member()
        self.start_thread()
        for url in [reverse('forum:index'), self.cat.get_absolute_url(), reverse('forum:search') + '?q=rule',
                    reverse('forum:profile'), reverse('past_problems'), reverse('training_resources')]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get(reverse('forum:search') + '?q=apply'), 'Rule 14 question')
