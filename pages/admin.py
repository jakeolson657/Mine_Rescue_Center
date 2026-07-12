from django.contrib import admin
from .models import (
    CalendarEvent, Competition, CompetitionProblem, ProblemDocument,
    SiteConfiguration, InstructionGuide, CompetitionRuleDocument, Scorecard,
)

admin.site.site_header = "Mine Rescue Center Administration"
admin.site.site_title = "Mine Rescue Center Admin"
admin.site.index_title = "Site Management"


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    # Singleton: one row of site-wide settings, no add/delete.
    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'location')
    list_filter = ('start_date',)
    search_fields = ('title', 'location')
    ordering = ('-start_date',)


class CompetitionProblemInline(admin.TabularInline):
    model = CompetitionProblem
    extra = 1
    fields = ('sort_order', 'title')
    ordering = ('sort_order', 'title')
    show_change_link = True  # click through to the problem to manage its documents


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'calendar_event', 'problem_count')
    list_filter = ('year',)
    search_fields = ('name', 'description', 'calendar_event__title', 'calendar_event__location')
    ordering = ('-year', 'name')
    inlines = [CompetitionProblemInline]
    actions = ['match_calendar_events']

    @admin.action(description="Find matching calendar event for selected competitions")
    def match_calendar_events(self, request, queryset):
        linked = 0
        for competition in queryset.filter(calendar_event__isnull=True):
            match = competition.find_calendar_event()
            if match:
                competition.calendar_event = match
                competition.save(update_fields=['calendar_event'])
                linked += 1
        self.message_user(request, f"Linked {linked} competition(s) to a calendar event.")


class ProblemDocumentInline(admin.TabularInline):
    model = ProblemDocument
    extra = 1
    fields = ('sort_order', 'title', 'file')
    ordering = ('sort_order', 'title')


@admin.register(CompetitionProblem)
class CompetitionProblemAdmin(admin.ModelAdmin):
    list_display = ('title', 'competition', 'sort_order', 'document_count')
    list_filter = ('competition',)
    search_fields = ('title', 'competition__name', 'description')
    ordering = ('competition', 'sort_order', 'title')
    inlines = [ProblemDocumentInline]


@admin.register(InstructionGuide)
class InstructionGuideAdmin(admin.ModelAdmin):
    list_display = ('title', 'sort_order', 'updated_at')
    search_fields = ('title', 'description')
    ordering = ('sort_order', 'title')


@admin.register(CompetitionRuleDocument)
class CompetitionRuleDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'sort_order', 'updated_at')
    search_fields = ('title',)
    ordering = ('sort_order', 'title')


@admin.register(Scorecard)
class ScorecardAdmin(admin.ModelAdmin):
    list_display = ('title', 'sort_order', 'updated_at')
    search_fields = ('title',)
    ordering = ('sort_order', 'title')
