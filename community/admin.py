from django.contrib import admin

from .models import Post, Thread, Feedback, PostReport, MutedUser


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
    list_display = ['user', 'rating', 'short_message', 'page', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'message']
    readonly_fields = ['user', 'rating', 'message', 'page', 'created_at']
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
