from django.contrib import admin

from studyflow.admin_export import export_as_csv

from django.utils import timezone

from .models import Post, Thread, Feedback, PostReport, MutedUser, ChatRoomConfig, DirectMessage
from .feedback_reply import save_feedback_reply


class PostInline(admin.TabularInline):
    model = Post
    extra = 0


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'course_code', 'created_by', 'created_at')
    list_filter = ('course_code',)
    search_fields = ('title', 'course_code')
    inlines = [PostInline]


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    actions = ['export_as_csv']
    export_as_csv = export_as_csv
    list_display = ['user', 'rating', 'short_message', 'replied', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'message', 'reply']
    readonly_fields = ['user', 'rating', 'message', 'page', 'created_at', 'replied_at', 'replied_by']
    fields = ['user', 'rating', 'message', 'page', 'created_at', 'reply', 'replied_at', 'replied_by']

    def replied(self, obj):
        return bool(obj.reply)
    replied.boolean = True

    def save_model(self, request, obj, form, change):
        if change and 'reply' in form.changed_data:
            save_feedback_reply(obj, request.user, obj.reply)
        else:
            super().save_model(request, obj, form, change)
    ordering = ['-created_at']

    def short_message(self, obj):
        return obj.message[:60] + '…' if len(obj.message) > 60 else obj.message
    short_message.short_description = 'Message'

    def has_add_permission(self, request):
        return False


@admin.register(PostReport)
class PostReportAdmin(admin.ModelAdmin):
    list_display = ['reporter', 'post', 'reason', 'reviewed', 'created_at']
    list_filter = ['reason', 'reviewed', 'created_at']
    search_fields = ['reporter__username']
    actions = ['mark_reviewed']

    def mark_reviewed(self, request, queryset):
        queryset.update(reviewed=True)
    mark_reviewed.short_description = 'Mark selected reports as reviewed'


@admin.register(MutedUser)
class MutedUserAdmin(admin.ModelAdmin):
    list_display = ['muter', 'muted', 'created_at']
    search_fields = ['muter__username', 'muted__username']


@admin.register(ChatRoomConfig)
class ChatRoomConfigAdmin(admin.ModelAdmin):
    list_display = ('slug', 'announcements_only', 'slow_mode_seconds')
    list_editable = ('announcements_only', 'slow_mode_seconds')


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'short_text', 'created_at', 'read_at')
    search_fields = ('sender__username', 'recipient__username', 'text')
    readonly_fields = ('sender', 'recipient', 'text', 'created_at', 'read_at')

    def short_text(self, obj):
        return obj.text[:60]

    def has_add_permission(self, request):
        return False
