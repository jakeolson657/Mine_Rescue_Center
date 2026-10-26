"""Forum emails. Sending is best-effort: a mail failure is logged and never
stops a post from being saved."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from .models import Status, Subscription

log = logging.getLogger(__name__)


def _send(subject, body, to):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to)
    except Exception:
        log.exception('Forum email failed: %s', subject)
        return False
    return True


def send_signin_link(email, url):
    """Unlike the other emails this one must succeed, so the caller can tell
    the visitor when it didn't."""
    body = (
        "Use this link to sign in to the Mine Rescue Center forum:\n\n"
        f"{url}\n\n"
        "The link works once and expires in 30 minutes. If you didn't ask to "
        "sign in, you can ignore this email.\n"
    )
    send_mail('Your Mine Rescue Center sign-in link', body, settings.DEFAULT_FROM_EMAIL, [email])


def notify_moderator_pending(request, post):
    admin_url = request.build_absolute_uri(
        reverse('admin:forum_post_changelist') + '?status__exact=pending'
    )
    body = (
        f"A post by {post.author.forum_profile} is waiting for approval in "
        f"“{post.thread.title}”:\n\n{post.body[:1500]}\n\n"
        f"Review the queue: {admin_url}\n"
    )
    _send('Forum post awaiting approval', body, [settings.FEEDBACK_TO_EMAIL])


def notify_moderator_report(request, report):
    post = report.post
    hidden = ' (now hidden automatically)' if post.status == Status.HIDDEN else ''
    body = (
        f"{report.reporter.forum_profile} reported a post by {post.author.forum_profile if post.author else 'a deleted member'}"
        f"{hidden} in “{post.thread.title}”.\n\nReason: {report.reason}\n\n"
        f"Post:\n{post.body[:1500]}\n\n"
        f"View it: {request.build_absolute_uri(post.get_absolute_url())}\n"
        f"Reports: {request.build_absolute_uri(reverse('admin:forum_report_changelist'))}\n"
    )
    _send('Forum post reported', body, [settings.FEEDBACK_TO_EMAIL])


def notify_subscribers(request, post):
    """Email everyone following the thread, except the post's author."""
    subs = (
        Subscription.objects.filter(thread=post.thread)
        .exclude(user=post.author)
        .select_related('user__forum_profile')
    )
    url = request.build_absolute_uri(post.get_absolute_url())
    profile_url = request.build_absolute_uri(reverse('forum:profile'))
    for sub in subs:
        profile = getattr(sub.user, 'forum_profile', None)
        if not sub.user.email or (profile and not profile.email_on_reply):
            continue
        body = (
            f"{post.author.forum_profile} replied to “{post.thread.title}”:\n\n"
            f"{post.body[:1500]}\n\n"
            f"Read the thread: {url}\n\n"
            f"To stop these emails, unfollow the thread or turn off reply "
            f"emails on your profile: {profile_url}\n"
        )
        _send(f'New reply: {post.thread.title}', body, [sub.user.email])
