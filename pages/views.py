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
)
from .forms import FeedbackForm, ProblemSubmissionForm
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
        .prefetch_related('problems__documents')
    )
    # Within a year: calendar order first, undated competitions last (by name).
    competitions.sort(key=lambda c: (
        c.start_date is None, c.start_date or date.min, c.name.lower()
    ))

    # Tag each problem with its discipline slugs for the client-side filter,
    # and bundle its documents as data. The document rows are rendered on the
    # client when a problem is opened, so the full archive page stays light.
    for competition in competitions:
        for problem in competition.problems.all():
            problem.category_csv = ' '.join(
                categorize_problem(problem.title, competition.name)
            )
            problem.docs_data = [
                {'title': d.title, 'url': d.file.url, 'kind': d.preview_kind}
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


def about(request):
    return render(request, 'about.html')


def training_resources(request):
    return render(request, 'coming_soon.html', {
        'meta_title': 'Training Resources',
        'eyebrow': 'Mine Rescue Center',
        'heading': 'Training Resources',
        'lede': 'A growing library of mine rescue training material.',
    })


def updates(request):
    return render(request, 'coming_soon.html', {
        'meta_title': 'Updates',
        'eyebrow': 'Mine Rescue Center',
        'heading': 'Updates',
        'lede': 'News and announcements from the Mine Rescue Center.',
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

        cal = Calendar(firstweekday=6).monthdayscalendar(year, month)
        context['calendar'] = cal

        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

        # All events that overlap with this month
        events = CalendarEvent.objects.filter(
            start_date__lte=last_day,
            end_date__gte=first_day,
        )

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
        return context


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
