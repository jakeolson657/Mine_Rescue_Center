from django.contrib import admin
from .models import CalendarEvent, CompetitionProblem, ProblemDocument

admin.site.site_header = "Mine Rescue Center Administration"
admin.site.site_title = "Mine Rescue Center Admin"
admin.site.index_title = "Site Management"


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'location')
    list_filter = ('start_date',)
    search_fields = ('title', 'location')
    ordering = ('-start_date',)


class ProblemDocumentInline(admin.TabularInline):
    model = ProblemDocument
    extra = 1
    fields = ('title', 'file')


@admin.register(CompetitionProblem)
class CompetitionProblemAdmin(admin.ModelAdmin):
    list_display = ('title', 'competition', 'year', 'document_count')
    list_filter = ('year',)
    search_fields = ('title', 'competition', 'description')
    ordering = ('-year', 'competition', 'title')
    inlines = [ProblemDocumentInline]
