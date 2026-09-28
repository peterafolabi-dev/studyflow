from django.contrib import admin

from .models import Course, Task, TimetableEntry


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'user', 'created_at')
    list_filter = ('user',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'due_date', 'is_done')
    list_filter = ('is_done', 'course')


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'day_of_week', 'start_time', 'end_time', 'location')
    list_filter = ('day_of_week', 'user')
