from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils.text import slugify
from django.views.generic import ListView, DetailView
from django.utils import timezone
from datetime import date, timedelta
from calendar import Calendar, month_name, monthrange
from .models import (
    CalendarEvent, Competition, SiteConfiguration,
    PROBLEM_CATEGORIES, categorize_problem,
    InstructionGuide, CompetitionRuleDocument, Scorecard,
    Quiz, BenchingApparatus, FirstAidResource, RopeRescueResource,
)
from .forms import FeedbackForm, ProblemSubmissionForm
from .geo import MAP_HEIGHT, MAP_WIDTH, is_surface, map_markers
from .search import search_events, state_name
from .calendar_export import (
    build_event_ics, google_calendar_url, outlook_calendar_url,
)


def landing_page(request):
    return render(request, 'landing.html')


def _send_problem_submission_email(data):
    """Email a visitor's problem submission to the team, with their files
    attached. Mirrors the feedback email path (same SMTP config)."""
    email = data.get('email') or ''
    files = data.get('files') or []
    body = "\n".join([
        f"Competition: {data['competition_name']}",
        f"Year:        {data.get('year') or '(not provided)'}",
        f"Location:    {data.get('location') or '(not provided)'}",
        f"Submitted by: {data.get('name') or '(not provided)'}",
        f"Email:       {email or '(not provided)'}",
        f"Files:       {len(files)} attached" if files else "Files:       (none)",
        "",
        "Context / details:",
        data['context'],
    ])
    message = EmailMessage(
        # Collapse newlines: a CharField can contain them and headers can't.
        subject="New problem submission: " + " ".join(
            data['competition_name'].split()
        ),
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.FEEDBACK_TO_EMAIL],
        reply_to=[email] if email else None,
    )
    for upload in files:
        message.attach(
            upload.name, upload.read(),
            upload.content_type or 'application/octet-stream',
        )
    message.send(fail_silently=False)


def past_problems(request):
    form = ProblemSubmissionForm()
    submit_error = False

    if request.method == 'POST':
        form = ProblemSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            # Honeypot filled => treat as spam: show success, send nothing.
            if form.cleaned_data['website']:
                return redirect(f"{reverse('past_problems')}?submitted=1#contribute")
            try:
                _send_problem_submission_email(form.cleaned_data)
            except Exception:
                submit_error = True
            else:
                return redirect(f"{reverse('past_problems')}?submitted=1#contribute")

    competitions = list(
        Competition.objects
        .select_related('calendar_event')
        .prefetch_related('problems__documents', 'problems__quizzes')
    )
    # Within a year: most recent first, undated competitions last (by name).
    # A competition without an event can still be placed via its sort_date.
    # Practice-problem collections always sink to the very bottom of the year.
    def listing_date(c):
        return c.start_date or c.sort_date

    competitions.sort(key=lambda c: (
        'practice' in c.name.lower(),
        listing_date(c) is None,
        -listing_date(c).toordinal() if listing_date(c) else 0,
        c.name.lower(),
    ))

    # Tag each problem with its discipline slugs for the client-side filter,
    # and bundle its documents as data. The document rows are rendered on the
    # client when a problem is opened, so the full archive page stays light.
    for competition in competitions:
        competition.state_name = state_name(competition.location)
        for problem in competition.problems.all():
            problem.category_csv = ' '.join(
                categorize_problem(problem.title, competition.name)
            )
            quiz_by_doc_id = {
                q.source_document_id: q.pk for q in problem.quizzes.all() if q.source_document_id
            }
            problem.docs_data = [
                {
                    'title': d.title, 'url': d.file.url, 'kind': d.preview_kind,
                    'quiz_url': reverse('quiz_detail', args=[quiz_by_doc_id[d.pk]]) if d.pk in quiz_by_doc_id else None,
                    'key_url': d.answer_key.url if d.answer_key else None,
                    'key_kind': d.answer_key_kind,
                }
                for d in problem.documents.all()
            ]
            problem.docs_script_id = f'docs-{problem.pk}'

    by_year = {}
    for competition in competitions:
        by_year.setdefault(competition.year, []).append(competition)

    # Most recent year first; competitions without a year at the bottom.
    year_groups = [
        {'year': year, 'competitions': by_year[year]}
        for year in sorted(by_year, key=lambda y: (y is None, -(y or 0)))
    ]
    return render(request, 'past_problems.html', {
        'year_groups': year_groups,
        'categories': PROBLEM_CATEGORIES,
        'form': form,
        'submitted': request.GET.get('submitted') == '1',
        'submit_error': submit_error,
    })


def quiz_detail(request, pk):
    quiz = get_object_or_404(
        Quiz.objects.select_related('problem__competition'), pk=pk
    )
    quiz_data = [
        {
            'text': q.text,
            'image': q.image.url if q.image else None,
            'choices': [{'text': c.text, 'is_correct': c.is_correct} for c in q.choices.all()],
        }
        for q in quiz.questions.prefetch_related('choices')
    ]
    return render(request, 'quiz.html', {
        'quiz': quiz,
        'quiz_data': quiz_data,
    })


def about(request):
    return render(request, 'about.html')


def training_resources(request):
    benching_apparatus = list(BenchingApparatus.objects.prefetch_related('resources'))
    for unit in benching_apparatus:
        unit.manual_resources = [r for r in unit.resources.all() if not r.is_sds]
        unit.sds_resources = [r for r in unit.resources.all() if r.is_sds]

    return render(request, 'training.html', {
        'instruction_guides': InstructionGuide.objects.all(),
        'rule_documents': CompetitionRuleDocument.objects.all(),
        'scorecards': Scorecard.objects.all(),
        'first_aid_resources': FirstAidResource.objects.all(),
        'rope_rescue_resources': RopeRescueResource.objects.all(),
        'benching_apparatus': benching_apparatus,
    })


class CalendarView(ListView):
    model = CalendarEvent
    template_name = 'calendar.html'
    context_object_name = 'events'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        year = self.request.GET.get('year', timezone.now().year)
        month = self.request.GET.get('month', timezone.now().month)

        try:
            year = int(year)
            month = int(month)
        except (ValueError, TypeError):
            year = timezone.now().year
            month = timezone.now().month

        context['year'] = year
        context['month'] = month
        context['month_name'] = month_name[month]

        today = timezone.localdate()
        context['today_year'] = today.year
        context['today_month'] = today.month

        context['msha_calendar_url'] = SiteConfiguration.load().msha_calendar_url

        query = self.request.GET.get('q', '').strip()
        context['search_query'] = query
        if query:
            context['search_results'], context['search_total'] = search_events(query)

        cal = Calendar(firstweekday=6).monthdayscalendar(year, month)
        context['calendar'] = cal

        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

        # All events that overlap with this month
        # Earliest-starting event on top; among events that start the same day,
        # the longer one (later end date) on top.
        events = CalendarEvent.objects.filter(
            start_date__lte=last_day,
            end_date__gte=first_day,
        ).order_by('start_date', '-end_date')

        events_by_day = {}
        for event in events:
            span_start = max(event.start_date, first_day)
            span_end = min(event.end_date, last_day)
            current = span_start
            while current <= span_end:
                day = current.day
                if day not in events_by_day:
                    events_by_day[day] = []
                events_by_day[day].append(event)
                current += timedelta(days=1)

        context['events_by_day'] = events_by_day

        # Map under the calendar: every contest in the shown year, colored by
        # surface vs. underground.
        year_events = list(CalendarEvent.objects.filter(
            start_date__lte=date(year, 12, 31),
            end_date__gte=date(year, 1, 1),
        ).order_by('start_date', '-end_date'))
        for event in year_events:
            event.is_surface = is_surface(event)
        markers, _ = map_markers(year_events)
        for marker in markers:
            kinds = {e.is_surface for p in marker['places'] for e in p['events']}
            marker['kind'] = ('mixed' if len(kinds) > 1
                              else 'surface' if True in kinds else 'underground')
            r = marker['r'] = 6 + 1.5 * min(marker['count'] - 1, 4)
            marker['halo'] = r + 9  # larger invisible hit area
            if marker['kind'] == 'mixed':
                # Split dot: surface on the left half, underground on the right.
                x, y = marker['x'], marker['y']
                top, bottom = f"M{x},{y - r:.1f}", f"{x},{y + r:.1f}Z"
                marker['surface_half'] = f"{top}A{r},{r} 0 0 0 {bottom}"
                marker['underground_half'] = f"{top}A{r},{r} 0 0 1 {bottom}"
            marker['left'] = round(marker['x'] / MAP_WIDTH * 100, 2)
            marker['top'] = round(marker['y'] / MAP_HEIGHT * 100, 2)
        context['map_markers'] = markers
        context['map_kinds'] = {m['kind'] for m in markers}

        if month == 1:
            context['prev_month'] = 12
            context['prev_year'] = year - 1
        else:
            context['prev_month'] = month - 1
            context['prev_year'] = year

        if month == 12:
            context['next_month'] = 1
            context['next_year'] = year + 1
        else:
            context['next_month'] = month + 1
            context['next_year'] = year

        return context


class EventDetailView(DetailView):
    model = CalendarEvent
    template_name = 'event_detail.html'
    context_object_name = 'event'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        detail_url = self.request.build_absolute_uri(
            reverse('event_detail', args=[event.pk])
        )
        context['google_url'] = google_calendar_url(event, url=detail_url)
        context['outlook_url'] = outlook_calendar_url(event, url=detail_url)
        context['ics_url'] = reverse('event_ics', args=[event.pk])

        # Deep-link to this contest's posted problems, but only once some have
        # been uploaded. An event can be linked from more than one competition;
        # pick the most recent one that actually has problems.
        competitions = (
            event.competitions.prefetch_related('problems').order_by('-year', 'name')
        )
        context['problems_competition'] = next(
            (c for c in competitions if c.problems.all()), None
        )
        return context


# Live results under the calendar search box (same list a full search shows).
SEARCH_PREVIEW_LIMIT = 8


def calendar_search(request):
    query = request.GET.get('q', '').strip()
    results, total = search_events(query, limit=SEARCH_PREVIEW_LIMIT) if query else ([], 0)
    return render(request, 'partials/calendar_search_results.html', {
        'search_query': query,
        'search_results': results,
        'search_total': total,
        'preview': True,
    })


def event_ics(request, pk):
    """Download a single event as an .ics file (Apple Calendar, Outlook
    desktop, Google import, and any other calendar app that reads iCalendar)."""
    event = get_object_or_404(CalendarEvent, pk=pk)
    detail_url = request.build_absolute_uri(
        reverse('event_detail', args=[event.pk])
    )
    response = HttpResponse(
        build_event_ics(event, url=detail_url),
        content_type='text/calendar; charset=utf-8',
    )
    name = slugify(event.title) or f'event-{event.pk}'
    response['Content-Disposition'] = f'attachment; filename="{name}.ics"'
    return response


def _send_feedback_email(data):
    email = data.get('email') or ''
    body = "\n".join([
        f"Name:  {data.get('name') or '(not provided)'}",
        f"Email: {email or '(not provided)'}",
        "",
        data['message'],
    ])
    EmailMessage(
        subject="New website feedback (minerescuecenter.com)",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.FEEDBACK_TO_EMAIL],
        reply_to=[email] if email else None,
    ).send(fail_silently=False)


def feedback(request):
    error = False
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            # Honeypot filled => treat as spam: show success, send nothing.
            if form.cleaned_data['website']:
                return redirect(f"{reverse('feedback')}?sent=1")
            try:
                _send_feedback_email(form.cleaned_data)
            except Exception:
                error = True
            else:
                return redirect(f"{reverse('feedback')}?sent=1")
    else:
        form = FeedbackForm()

    return render(request, 'feedback.html', {
        'form': form,
        'sent': request.GET.get('sent') == '1',
        'error': error,
    })
