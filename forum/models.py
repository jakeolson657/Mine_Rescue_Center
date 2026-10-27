from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from pages.models import CalendarEvent, CompetitionProblem, CompetitionRuleDocument, Quiz

# A member's first few posts wait in the moderation queue; once this many have
# been approved they post straight to the forum.
TRUST_AFTER_APPROVED_POSTS = 2

# Reports from this many different members hide a post until it is reviewed.
AUTO_HIDE_REPORTS = 3

# The forum's moderator is the site's own account, not whoever has admin
# access. Moderators approve, hide, and edit any post and wear the
# Moderator tag.
MODERATOR_EMAILS = {'info@minerescuecenter.com'}


def is_moderator(user):
    return bool(user and user.is_authenticated and (user.email or '').lower() in MODERATOR_EMAILS)


class ForumProfile(models.Model):
    """Forum identity for a site user. Created the first time someone signs in
    with an emailed link; the display name is required before posting."""

    ROLE_CHOICES = [
        ('member', 'Team member'),
        ('trainer', 'Trainer'),
        ('judge', 'Judge'),
        ('other', 'Other'),
    ]
    DISTRICT_CHOICES = [
        ('coal', 'Coal'),
        ('mnm', 'Metal/Nonmetal'),
        ('both', 'Coal & MNM'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_profile')
    display_name = models.CharField(max_length=50, blank=True)
    team = models.CharField(max_length=100, blank=True, help_text="Team or company the member belongs to")
    state = models.CharField(max_length=30, blank=True, help_text="e.g. WV")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, blank=True)
    district = models.CharField(max_length=5, choices=DISTRICT_CHOICES, blank=True)
    trusted = models.BooleanField(
        default=False,
        help_text="Trusted members' posts appear immediately. Set automatically "
                  f"after {TRUST_AFTER_APPROVED_POSTS} approved posts.",
    )
    banned = models.BooleanField(default=False, help_text="Banned members can read but not post.")
    email_on_reply = models.BooleanField(default=True, help_text="Email me when someone replies to a thread I follow.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name or self.user.email or self.user.username

    @property
    def is_complete(self):
        return bool(self.display_name)

    @property
    def posts_freely(self):
        return self.trusted or self.is_moderator

    @property
    def is_moderator(self):
        return is_moderator(self.user)

    @property
    def meta_line(self):
        """Short context shown beside a member's name, e.g. 'Coal · WV · Example Mine'."""
        parts = [self.get_district_display(), self.state, self.team]
        return ' · '.join(p for p in parts if p)


def profile_for(user):
    profile, _ = ForumProfile.objects.get_or_create(user=user)
    return profile


class Category(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    description = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('forum:category', args=[self.slug])


class Status(models.TextChoices):
    VISIBLE = 'visible', 'Visible'
    PENDING = 'pending', 'Awaiting approval'
    HIDDEN = 'hidden', 'Hidden'


class Thread(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='threads')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='forum_threads')
    title = models.CharField(max_length=150)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VISIBLE)
    pinned = models.BooleanField(default=False)
    locked = models.BooleanField(default=False, help_text="Locked threads take no new replies.")

    # What the thread is about, if it's tied to something in the archive.
    # At most one is set.
    problem = models.ForeignKey(CompetitionProblem, null=True, blank=True, on_delete=models.SET_NULL, related_name='forum_threads')
    rule_doc = models.ForeignKey(CompetitionRuleDocument, null=True, blank=True, on_delete=models.SET_NULL, related_name='forum_threads')
    quiz = models.ForeignKey(Quiz, null=True, blank=True, on_delete=models.SET_NULL, related_name='forum_threads')
    event = models.ForeignKey(CalendarEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name='forum_threads')

    reply_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    last_post_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-pinned', '-last_post_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('forum:thread', args=[self.pk, slugify(self.title)[:60] or 'thread'])

    @property
    def linked(self):
        """(kind label, title, url) for the archive item this thread is about,
        or None."""
        if self.problem_id:
            p = self.problem
            return ('Problem', str(p.competition) + ' — ' + p.title,
                    reverse('past_problems') + f'#comp-{p.competition_id}')
        if self.quiz_id:
            q = self.quiz
            return ('Written test', f'{q.problem.competition} — {q.title}', reverse('quiz_detail', args=[q.pk]))
        if self.rule_doc_id:
            return ('Contest rules', self.rule_doc.title, reverse('training_resources') + '#rules')
        if self.event_id:
            return ('Event', str(self.event), reverse('event_detail', args=[self.event_id]))
        return None

    def refresh_counts(self):
        visible = self.posts.filter(status=Status.VISIBLE)
        self.reply_count = max(visible.count() - 1, 0)
        last = visible.order_by('-created_at').first()
        if last:
            self.last_post_at = last.created_at
        self.save(update_fields=['reply_count', 'last_post_at'])


class Post(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='forum_posts')
    body = models.TextField(max_length=10000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VISIBLE)
    is_answer = models.BooleanField(default=False, help_text="Marked as the accepted answer to the thread's question.")
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.author} in “{self.thread}”'

    @property
    def is_opening(self):
        first = self.thread.posts.order_by('created_at').values_list('pk', flat=True).first()
        return first == self.pk

    def get_absolute_url(self):
        return self.thread.get_absolute_url() + f'#post-{self.pk}'

    def approve(self):
        """Publish a queued post (and its thread, if it opened one). Returns
        True when the post was newly published."""
        if self.status == Status.VISIBLE:
            return False
        self.status = Status.VISIBLE
        self.save(update_fields=['status'])
        thread = self.thread
        if self.is_opening and thread.status != Status.VISIBLE:
            thread.status = Status.VISIBLE
            thread.save(update_fields=['status'])
        thread.refresh_counts()
        if self.author_id:
            profile = profile_for(self.author)
            approved = Post.objects.filter(author=self.author, status=Status.VISIBLE).count()
            if not profile.trusted and approved >= TRUST_AFTER_APPROVED_POSTS:
                profile.trusted = True
                profile.save(update_fields=['trusted'])
        return True

    def hide(self):
        self.status = Status.HIDDEN
        self.save(update_fields=['status'])
        if self.is_opening:
            self.thread.status = Status.HIDDEN
            self.thread.save(update_fields=['status'])
        self.thread.refresh_counts()


class Report(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    reason = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['resolved', '-created_at']
        constraints = [models.UniqueConstraint(fields=['post', 'reporter'], name='one_report_per_member')]

    def __str__(self):
        return f'Report on post {self.post_id}: {self.reason[:40]}'


class Subscription(models.Model):
    """A member following a thread gets an email when someone replies."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_subscriptions')
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='subscriptions')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'thread'], name='one_subscription_per_thread')]
