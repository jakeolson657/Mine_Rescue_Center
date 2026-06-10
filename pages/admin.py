from django.contrib import admin
from .models import CalendarEvent, PastProblem

admin.site.site_header = "Mine Rescue Center Administration"
admin.site.site_title = "Mine Rescue Center Admin"
admin.site.index_title = "Site Management"


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'location')
    list_filter = ('start_date',)
    search_fields = ('title', 'location')
    ordering = ('-start_date',)


@admin.register(PastProblem)
class PastProblemAdmin(admin.ModelAdmin):
    list_display = ('title', 'competition', 'year', 'filename', 'uploaded_at')
    list_filter = ('year',)
    search_fields = ('title', 'competition', 'description')
    ordering = ('-year', 'title')
