import math
from collections import Counter
from functools import wraps
from itertools import combinations
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from pages.geo import NORTH_AMERICA_HEIGHT, NORTH_AMERICA_WIDTH, map_markers, project_north_america
from pages.models import CalendarEvent, CompetitionProblem, CompetitionRuleDocument, Quiz

from . import notify, signin
from .forms import (
    STATE_OPTIONS, EditPostForm, ProfileForm, ReplyForm, ReportForm, SignInForm, TeamListingForm, ThreadForm,
)
from .models import (
    AUTO_HIDE_REPORTS, Category, Post, Report, Status, Subscription, TeamListing, Thread, is_moderator, profile_for,
)

# Archive items a thread can be about: URL kind -> (Thread field, model,
# category slug a new thread defaults to).
LINK_KINDS = {
    'problem': ('problem', CompetitionProblem, 'problems'),
    'quiz': ('quiz', Quiz, 'written-tests'),
    'rule': ('rule_doc', CompetitionRuleDocument, 'rules'),
    'event': ('event', CalendarEvent, 'events'),
}

REMEMBER_DEVICE_SECONDS = 365 * 24 * 60 * 60
STATE_NAMES = {abbr: name for name, abbr in STATE_OPTIONS}

# Team map pin sizes, in map units. Pins combine when they're closer than this
# share of the distance at which their edges would just touch.
TEAM_PIN_RADIUS = 6
SHARED_TEAM_PIN_RADIUS = 10
TEAM_PIN_CROWDED = 0.9


def old_address_redirect(request, rest=''):
    """Forward a /forum/... link to the same page under /community/, keeping
    its query string. Forms submitted from a page left open keep their data."""
    new_url = reverse('forum:index') + request.get_full_path().removeprefix('/forum/')
    return HttpResponsePermanentRedirect(new_url, preserve_request=request.method not in ('GET', 'HEAD'))


# ---------- helpers ----------

def _safe_next(request, url, default=None):
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return default or reverse('forum:index')


def _account_gate(view, needs_display_name):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse('forum:signin') + '?' + urlencode({'next': request.get_full_path()}))
        profile = profile_for(request.user)
        if needs_display_name and not profile.is_complete:
            return redirect(reverse('forum:profile') + '?' + urlencode({'next': request.get_full_path()}))
        if profile.banned:
            messages.error(request, "Your account can't post in the community. Contact info@minerescuecenter.com if you think this is a mistake.")
            return redirect('forum:index')
        request.forum_profile = profile
        return view(request, *args, **kwargs)
    return wrapped


def member_required(view):
    """Signed in, with a display name set, and not banned."""
    return _account_gate(view, needs_display_name=True)


def account_required(view):
    """Signed in and not banned. For pages that never show the member's name."""
    return _account_gate(view, needs_display_name=False)


def _readable_threads(user):
    """Threads this visitor may open: visible ones, plus their own queued ones
    (moderators see everything)."""
    qs = Thread.objects.all()
    if is_moderator(user):
        return qs
    if user.is_authenticated:
        return qs.filter(Q(status=Status.VISIBLE) | Q(author=user, status=Status.PENDING))
    return qs.filter(status=Status.VISIBLE)


def _thread_list(qs):
    return (
        qs.select_related('category', 'author__forum_profile')
        .annotate(has_answer=Count('posts', filter=Q(posts__is_answer=True, posts__status=Status.VISIBLE)))
        # Meta.ordering doesn't apply to aggregate queries, so restate it.
        .order_by('-pinned', '-last_post_at')
    )


def _link_from(params):
    """(kind, object) named by ?problem=12 / ?quiz=… etc, or (None, None)."""
    for kind, (_, model, _) in LINK_KINDS.items():
        value = params.get(kind)
        if value and str(value).isdigit():
            return kind, get_object_or_404(model, pk=value)
    return None, None


def _contest_not_held_yet(obj):
    """True for a problem/test whose competition hasn't happened yet, so the
    forum can't become the place a contest problem leaks early."""
    problem = obj.problem if isinstance(obj, Quiz) else obj if isinstance(obj, CompetitionProblem) else None
    if problem is None:
        return False
    start = problem.competition.start_date
    return bool(start and start > timezone.localdate())


def _link_title(kind, obj):
    if kind == 'problem':
        return f'{obj.competition} — {obj.title}'
    if kind == 'quiz':
        return f'{obj.problem.competition} — {obj.title}'
    return str(obj)


def _publish(request, post, new_thread=False):
    """After saving a post: follow the thread, then notify people."""
    Subscription.objects.get_or_create(user=request.user, thread=post.thread)
    if post.status == Status.VISIBLE:
        post.thread.refresh_counts()
        if not new_thread:
            notify.notify_subscribers(request, post)
    else:
        notify.notify_moderator_pending(request, post)
        messages.info(
            request,
            "Thanks! New members' first posts are checked by a moderator before "
            "they appear — usually within a day. You can see it below in the meantime.",
        )


def _team_kind(teams):
    """A pin's color: the team type, or 'mixed' when it holds several types."""
    types = {team.team_type for team in teams}
    return types.pop() if len(types) == 1 else 'mixed'


def _team_pin_radius(count):
    return SHARED_TEAM_PIN_RADIUS if count > 1 else TEAM_PIN_RADIUS


def _combine_crowded_pins(pins):
    """Merge the closest overlapping pins, one pair at a time, until none are
    crowded. A combined pin sits between its teams and is larger, so it can
    crowd its neighbors in turn."""
    while True:
        crowded = [
            (math.dist((a['x'], a['y']), (b['x'], b['y'])), i, j)
            for (i, a), (j, b) in combinations(enumerate(pins), 2)
            if math.dist((a['x'], a['y']), (b['x'], b['y']))
            < TEAM_PIN_CROWDED * (_team_pin_radius(a['count']) + _team_pin_radius(b['count']))
        ]
        if not crowded:
            return pins
        _, i, j = min(crowded)
        keep, absorbed = pins[i], pins.pop(j)
        count = keep['count'] + absorbed['count']
        keep['x'] = round((keep['x'] * keep['count'] + absorbed['x'] * absorbed['count']) / count, 1)
        keep['y'] = round((keep['y'] * keep['count'] + absorbed['y'] * absorbed['count']) / count, 1)
        keep['count'] = count
        keep['places'] += absorbed['places']


def _team_map():
    """(national pins, town pins, list rows) for the approved teams.

    Each town gets its own national pin unless pins would crowd each other.
    Opening a state swaps those for one pin per town, and each list row names
    its town and state so the list can narrow to match."""
    markers, _ = map_markers(
        TeamListing.objects.filter(status=Status.VISIBLE), cluster_radius=0, projection=project_north_america,
    )
    markers = _combine_crowded_pins(markers)
    towns, rows = [], []
    for number, marker in enumerate(markers, 1):
        teams = [team for place in marker['places'] for team in place['events']]
        marker['number'] = number
        marker['radius'] = _team_pin_radius(marker['count'])
        marker['label'] = ', '.join(place['label'] for place in marker['places'])
        marker['kind'] = _team_kind(teams)
        # A pin can straddle a border, so it opens the state most of its teams are in.
        marker['state'] = STATE_NAMES.get(Counter(team.state for team in teams).most_common(1)[0][0], '')
        for place in marker['places']:
            town = {
                'number': len(towns) + 1,
                'label': place['label'],
                'name': place['label'].rsplit(', ', 1)[0],
                'x': round(place['x'], 1),
                'y': round(place['y'], 1),
                'count': len(place['events']),
                'kind': _team_kind(place['events']),
                'state': STATE_NAMES.get(place['events'][0].state, ''),
            }
            towns.append(town)
            rows.extend({'team': team, 'town': town['number'], 'state': town['state']} for team in place['events'])
    rows.sort(key=lambda row: (row['team'].state, row['team'].city.lower(), row['team'].name.lower()))
    return markers, towns, rows


# ---------- browsing ----------

def index(request):
    visible = Q(threads__status=Status.VISIBLE)
    categories = Category.objects.annotate(
        thread_count=Count('threads', filter=visible),
        last_activity=Max('threads__last_post_at', filter=visible),
    ).order_by('sort_order', 'name')
    recent = _thread_list(Thread.objects.filter(status=Status.VISIBLE)).order_by('-last_post_at')[:10]
    team_markers, team_towns, team_rows = _team_map()
    return render(request, 'forum/index.html', {
        'categories': categories,
        'recent': recent,
        'team_markers': team_markers,
        'team_towns': team_towns,
        'team_map_width': NORTH_AMERICA_WIDTH,
        'team_map_height': NORTH_AMERICA_HEIGHT,
        'team_rows': team_rows,
        'team_types': TeamListing.TEAM_TYPE_CHOICES,
        'has_mixed_pin': any(marker['kind'] == 'mixed' for marker in team_markers),
        'has_listing': request.user.is_authenticated and TeamListing.objects.filter(member=request.user).exists(),
    })


def category(request, slug):
    cat = get_object_or_404(Category, slug=slug)
    threads = _thread_list(_readable_threads(request.user).filter(category=cat))
    page = Paginator(threads, 25).get_page(request.GET.get('page'))
    return render(request, 'forum/category.html', {'category': cat, 'page': page})


def _render_thread(request, thread, reply_form=None, status=200):
    posts = thread.posts.select_related('author__forum_profile')
    user = request.user
    is_mod = is_moderator(user)
    if not is_mod:
        mine = Q(author=user, status=Status.PENDING) if user.is_authenticated else Q(pk__in=[])
        posts = posts.filter(Q(status=Status.VISIBLE) | mine)
    posts = list(posts)
    is_author = user.is_authenticated and thread.author_id == user.pk
    following = user.is_authenticated and thread.subscriptions.filter(user=user).exists()
    return render(request, 'forum/thread.html', {
        'thread': thread,
        'category': thread.category,
        'posts': posts,
        'opening_pk': posts[0].pk if posts else None,
        'answer': next((p for p in posts if p.is_answer and p.status == Status.VISIBLE), None),
        'can_mark_answer': is_author or is_mod,
        'is_mod': is_mod,
        'following': following,
        'reply_form': reply_form or ReplyForm(user=user),
        'report_form': ReportForm(),
    }, status=status)


def thread_detail(request, pk, slug=None):
    thread = get_object_or_404(
        _readable_threads(request.user).select_related('category', 'author__forum_profile'), pk=pk
    )
    canonical = thread.get_absolute_url()
    if request.path != canonical:
        return redirect(canonical, permanent=True)
    return _render_thread(request, thread)


def about(request, kind, pk):
    """Every thread about one archive item, with a button to start another."""
    if kind not in LINK_KINDS:
        raise Http404
    field, model, _ = LINK_KINDS[kind]
    obj = get_object_or_404(model, pk=pk)
    threads = _thread_list(_readable_threads(request.user).filter(**{field: obj}))
    return render(request, 'forum/about.html', {
        'kind': kind,
        'obj': obj,
        'link_title': _link_title(kind, obj),
        'threads': threads,
        'not_held_yet': _contest_not_held_yet(obj),
        'new_url': reverse('forum:new_thread') + '?' + urlencode({kind: obj.pk}),
    })


def search(request):
    q = ' '.join(request.GET.get('q', '').split())[:100]
    results = []
    if len(q) >= 2:
        matches = Q(title__icontains=q) | Q(posts__body__icontains=q, posts__status=Status.VISIBLE)
        results = _thread_list(
            Thread.objects.filter(status=Status.VISIBLE).filter(matches).distinct()
        ).order_by('-last_post_at')[:50]
    return render(request, 'forum/search.html', {'q': q, 'results': results})


# ---------- posting ----------

@member_required
def new_thread(request):
    source = request.POST if request.method == 'POST' else request.GET
    kind, obj = _link_from(source)
    if obj is not None and _contest_not_held_yet(obj):
        messages.error(request, "Discussion opens for a contest's problems once the contest has been held.")
        return redirect('forum:about', kind=kind, pk=obj.pk)

    if request.method == 'POST':
        form = ThreadForm(request.POST, user=request.user)
        if form.is_valid():
            if form.is_spam:
                return redirect('forum:index')
            status = Status.VISIBLE if request.forum_profile.posts_freely else Status.PENDING
            thread = Thread.objects.create(
                category=form.cleaned_data['category'],
                author=request.user,
                title=form.cleaned_data['title'],
                status=status,
                **({LINK_KINDS[kind][0]: obj} if obj is not None else {}),
            )
            post = Post.objects.create(thread=thread, author=request.user, body=form.cleaned_data['body'], status=status)
            _publish(request, post, new_thread=True)
            return redirect(thread)
    else:
        initial = {}
        cat_slug = request.GET.get('category') or (LINK_KINDS[kind][2] if kind else None)
        if cat_slug:
            initial['category'] = Category.objects.filter(slug=cat_slug).first()
        form = ThreadForm(initial=initial, user=request.user)

    return render(request, 'forum/new_thread.html', {
        'form': form,
        'link_kind': kind,
        'link_obj': obj,
        'link_title': _link_title(kind, obj) if obj is not None else '',
    })


@require_POST
@member_required
def reply(request, pk):
    thread = get_object_or_404(Thread.objects.select_related('category'), pk=pk, status=Status.VISIBLE)
    if thread.locked and not is_moderator(request.user):
        messages.error(request, "This thread is locked and isn't taking new replies.")
        return redirect(thread)
    form = ReplyForm(request.POST, user=request.user)
    if not form.is_valid():
        return _render_thread(request, thread, reply_form=form, status=400)
    if form.is_spam:
        return redirect(thread)
    status = Status.VISIBLE if request.forum_profile.posts_freely else Status.PENDING
    post = Post.objects.create(thread=thread, author=request.user, body=form.cleaned_data['body'], status=status)
    _publish(request, post)
    return redirect(post.get_absolute_url())


@member_required
def edit_post(request, pk):
    post = get_object_or_404(Post.objects.select_related('thread'), pk=pk)
    if not (post.author_id == request.user.pk or is_moderator(request.user)) or post.status == Status.HIDDEN:
        raise Http404
    if request.method == 'POST':
        form = EditPostForm(request.POST, user=request.user)
        if form.is_valid():
            post.body = form.cleaned_data['body']
            post.edited_at = timezone.now()
            # An edit from a member still on probation goes back through the
            # queue, so an approved post can't be swapped for spam.
            requeue = post.status == Status.VISIBLE and not request.forum_profile.posts_freely
            if requeue:
                post.status = Status.PENDING
            post.save()
            if requeue:
                if post.is_opening:
                    post.thread.status = Status.PENDING
                    post.thread.save(update_fields=['status'])
                post.thread.refresh_counts()
                notify.notify_moderator_pending(request, post)
                messages.info(request, "Saved. Your edit will appear once a moderator approves it.")
            return redirect(post.get_absolute_url())
    else:
        form = EditPostForm(initial={'body': post.body}, user=request.user)
    return render(request, 'forum/edit_post.html', {'form': form, 'post': post, 'thread': post.thread})


@require_POST
@member_required
def mark_answer(request, pk):
    post = get_object_or_404(Post.objects.select_related('thread'), pk=pk, status=Status.VISIBLE)
    thread = post.thread
    if not (thread.author_id == request.user.pk or is_moderator(request.user)) or post.is_opening:
        raise Http404
    was_answer = post.is_answer
    thread.posts.filter(is_answer=True).update(is_answer=False)
    if not was_answer:
        post.is_answer = True
        post.save(update_fields=['is_answer'])
    return redirect(post.get_absolute_url())


@require_POST
@member_required
def report_post(request, pk):
    post = get_object_or_404(Post.objects.select_related('thread'), pk=pk, status=Status.VISIBLE)
    form = ReportForm(request.POST)
    if not form.is_valid() or post.author_id == request.user.pk:
        messages.error(request, "Please say briefly what's wrong with the post.")
        return redirect(post.get_absolute_url())
    report, created = Report.objects.get_or_create(
        post=post, reporter=request.user, defaults={'reason': form.cleaned_data['reason']}
    )
    if created:
        open_reports = post.reports.filter(resolved=False).count()
        if open_reports >= AUTO_HIDE_REPORTS and not is_moderator(post.author):
            post.hide()
        notify.notify_moderator_report(request, report)
    messages.success(request, "Thanks — a moderator will take a look.")
    return redirect(post.thread if post.status == Status.HIDDEN else post.get_absolute_url())


@require_POST
@member_required
def toggle_follow(request, pk):
    thread = get_object_or_404(Thread, pk=pk, status=Status.VISIBLE)
    sub = Subscription.objects.filter(user=request.user, thread=thread)
    if sub.exists():
        sub.delete()
        messages.success(request, "You'll no longer get emails about this thread.")
    else:
        Subscription.objects.create(user=request.user, thread=thread)
        messages.success(request, "You'll get an email when someone replies.")
    return redirect(thread)


@require_POST
def moderate(request, pk):
    """Moderator shortcut on the thread page: approve, hide or delete a post.
    Deleting the opening post deletes the whole thread."""
    if not is_moderator(request.user):
        raise Http404
    post = get_object_or_404(Post.objects.select_related('thread__category'), pk=pk)
    action = request.POST.get('action')
    if action == 'delete':
        thread = post.thread
        if post.is_opening:
            thread.delete()
            messages.success(request, "Thread deleted.")
            return redirect(thread.category)
        post.delete()
        thread.refresh_counts()
        messages.success(request, "Post deleted.")
        return redirect(thread)
    if action == 'approve':
        notify.approve_and_notify(request, post)
        post.reports.update(resolved=True)
    elif action == 'hide':
        post.hide()
        post.reports.update(resolved=True)
    return redirect(post.get_absolute_url())


# ---------- accounts ----------

def signin_view(request):
    next_url = _safe_next(request, request.POST.get('next') or request.GET.get('next'))
    if request.user.is_authenticated:
        return redirect(next_url)
    sent_to = request.session.pop('forum_signin_sent', None)
    error = False
    if request.method == 'POST':
        form = SignInForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            # One email per address per minute; the honeypot gets a silent "sent".
            throttle_key = 'forum-signin:' + email
            if not form.is_spam and not cache.get(throttle_key):
                url = request.build_absolute_uri(
                    reverse('forum:signin_confirm') + '?' + urlencode({'t': signin.make_token(email, next_url)})
                )
                try:
                    notify.send_signin_link(email, url)
                except Exception:
                    error = True
                else:
                    cache.set(throttle_key, True, 60)
            if not error:
                request.session['forum_signin_sent'] = email
                return redirect(reverse('forum:signin') + '?' + urlencode({'next': next_url}))
    else:
        form = SignInForm()
    return render(request, 'forum/signin.html', {
        'form': form, 'next': next_url, 'sent_to': sent_to, 'error': error,
    })


def signin_confirm(request):
    """The emailed link lands here. Signing in takes a button press, so mail
    scanners that pre-open links can't use up the one-time token."""
    token = request.POST.get('t') or request.GET.get('t', '')
    data = signin.read_token(token)
    if data is None:
        return render(request, 'forum/signin_confirm.html', {'expired': True}, status=400)
    email, next_url = data
    if request.method == 'POST':
        user = signin.get_or_create_user(email)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        # Remembered devices stay signed in for a year; otherwise the
        # session ends when the browser closes.
        request.session.set_expiry(REMEMBER_DEVICE_SECONDS if request.POST.get('remember') else 0)
        next_url = _safe_next(request, next_url)
        if not profile_for(user).is_complete:
            return redirect(reverse('forum:profile') + '?' + urlencode({'next': next_url, 'welcome': 1}))
        return redirect(next_url)
    return render(request, 'forum/signin_confirm.html', {'email': email, 'token': token})


@require_POST
def signout(request):
    logout(request)
    return redirect('forum:index')


def profile(request):
    if not request.user.is_authenticated:
        return redirect(reverse('forum:signin') + '?' + urlencode({'next': request.get_full_path()}))
    prof = profile_for(request.user)
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=prof)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile saved.")
            return redirect(_safe_next(request, next_url, reverse('forum:profile')))
    else:
        form = ProfileForm(instance=prof)
    threads = _thread_list(_readable_threads(request.user).filter(author=request.user)).order_by('-last_post_at')[:30]
    return render(request, 'forum/profile.html', {
        'form': form,
        'profile': prof,
        'next': next_url,
        'welcome': request.GET.get('welcome') == '1' or not prof.is_complete,
        'threads': threads,
        'state_options': STATE_OPTIONS,
        'has_listing': TeamListing.objects.filter(member=request.user).exists(),
    })


# ---------- team map ----------

@account_required
def team_listing(request):
    """A member adds, updates, or checks on their team's place on the map."""
    listing = TeamListing.objects.filter(member=request.user).first()
    declined = listing is not None and listing.status == Status.HIDDEN
    if request.method == 'POST' and not declined:
        was_pending = listing is not None and listing.status == Status.PENDING
        form = TeamListingForm(request.POST, instance=listing)
        if form.is_valid():
            if listing is not None and not set(form.changed_data) - {'consent'}:
                messages.info(request, "Nothing changed.")
                return redirect('forum:team_listing')
            saved = form.save(commit=False)
            saved.member = request.user
            # Every change is reviewed, so an approved listing can't be
            # swapped for something else.
            saved.status = Status.PENDING
            saved.save()
            if not was_pending:
                notify.notify_moderator_team(request, saved)
            messages.success(request, "Thanks! Your team will appear on the map once a moderator approves it.")
            return redirect('forum:team_listing')
    elif listing is not None:
        form = TeamListingForm(instance=listing)
    else:
        profile = request.forum_profile
        form = TeamListingForm(initial={'name': profile.team, 'state': profile.state, 'sector': profile.district})
    return render(request, 'forum/team_listing.html', {'form': form, 'listing': listing, 'declined': declined})


@require_POST
@account_required
def remove_team_listing(request):
    TeamListing.objects.filter(member=request.user).delete()
    messages.success(request, "Your team has been removed from the map.")
    return redirect(reverse('forum:index') + '#teams')

