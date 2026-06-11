from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.utils import timezone
from datetime import date, timedelta
from calendar import Calendar, month_name, monthrange
from .models import CalendarEvent, Competition


def landing_page(request):
    return render(request, 'landing.html')


def past_problems(request):
    competitions = list(
        Competition.objects
        .select_related('calendar_event')
        .prefetch_related('problems__documents')
    )
    # Within a year: calendar order first, undated competitions last (by name).
    competitions.sort(key=lambda c: (
        c.start_date is None, c.start_date or date.min, c.name.lower()
    ))

    by_year = {}
    for competition in competitions:
        by_year.setdefault(competition.year, []).append(competition)

    # Most recent year first; competitions without a year at the bottom.
    year_groups = [
        {'year': year, 'competitions': by_year[year]}
        for year in sorted(by_year, key=lambda y: (y is None, -(y or 0)))
    ]
    return render(request, 'past_problems.html', {'year_groups': year_groups})


def about(request):
    return render(request, 'about.html')


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
