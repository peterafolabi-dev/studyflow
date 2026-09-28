from django.contrib import admin

from .models import Post, Thread


class PostInline(admin.TabularInline):
    model = Post
    extra = 0


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'course_code', 'created_by', 'created_at')
    list_filter = ('course_code',)
    search_fields = ('title', 'course_code')
    inlines = [PostInline]
