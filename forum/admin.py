from django.contrib import admin, messages
from django.utils.html import format_html

from . import notify
from .models import Category, ForumProfile, Post, Report, Status, Thread


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'sort_order']
    list_editable = ['sort_order']
    prepopulated_fields = {'slug': ['name']}


@admin.register(ForumProfile)
class ForumProfileAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'email', 'role', 'district', 'state', 'team', 'trusted', 'banned', 'created_at']
    list_editable = ['trusted', 'banned']
    list_filter = ['trusted', 'banned', 'role', 'district']
    search_fields = ['display_name', 'user__email', 'team']
    raw_id_fields = ['user']

    @admin.display(ordering='user__email')
    def email(self, obj):
        return obj.user.email


class PostInline(admin.TabularInline):
    model = Post
    fields = ['author', 'status', 'is_answer', 'created_at', 'body']
    raw_id_fields = ['author']
    extra = 0


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'status', 'pinned', 'locked', 'reply_count', 'last_post_at']
    list_editable = ['pinned', 'locked']
    list_filter = ['status', 'category', 'pinned', 'locked']
    search_fields = ['title']
    raw_id_fields = ['author', 'problem', 'rule_doc', 'quiz', 'event']
    inlines = [PostInline]


@admin.action(description='Approve (publish) selected posts')
def _approve(modeladmin, request, queryset):
    n = 0
    for post in queryset.select_related('thread', 'author'):
        if post.approve():
            n += 1
            if not post.is_opening:
                notify.notify_subscribers(request, post)
    Report.objects.filter(post__in=queryset).update(resolved=True)
    messages.success(request, f'Approved {n} post(s).')


@admin.action(description='Hide selected posts')
def _hide(modeladmin, request, queryset):
    for post in queryset:
        post.hide()
    Report.objects.filter(post__in=queryset).update(resolved=True)
    messages.success(request, f'Hid {queryset.count()} post(s).')


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['excerpt', 'author', 'thread', 'status', 'open_reports', 'created_at', 'view']
    list_filter = ['status', 'thread__category']
    search_fields = ['body', 'thread__title', 'author__email']
    raw_id_fields = ['thread', 'author']
    actions = [_approve, _hide]

    def excerpt(self, obj):
        return obj.body[:80] + ('…' if len(obj.body) > 80 else '')

    def open_reports(self, obj):
        return obj.reports.filter(resolved=False).count() or ''

    def view(self, obj):
        return format_html('<a href="{}" target="_blank">View</a>', obj.get_absolute_url())


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['reason', 'post_excerpt', 'reporter', 'post_status', 'resolved', 'created_at']
    list_filter = ['resolved']
    list_editable = ['resolved']
    raw_id_fields = ['post', 'reporter']
    actions = ['hide_posts', 'keep_posts']

    def post_excerpt(self, obj):
        return format_html('<a href="{}" target="_blank">{}</a>', obj.post.get_absolute_url(), obj.post.body[:60])

    def post_status(self, obj):
        return obj.post.get_status_display()

    @admin.action(description='Hide the reported posts and resolve')
    def hide_posts(self, request, queryset):
        for report in queryset.select_related('post'):
            report.post.hide()
        queryset.update(resolved=True)

    @admin.action(description='Keep the reported posts (restore if auto-hidden) and resolve')
    def keep_posts(self, request, queryset):
        for report in queryset.select_related('post'):
            if report.post.status == Status.HIDDEN:
                report.post.approve()
        queryset.update(resolved=True)
