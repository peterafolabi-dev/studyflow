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


from .models import CoachFeedback, CoachMemory


@admin.register(CoachFeedback)
class CoachFeedbackAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'helpful', 'mode', 'short_question', 'user', 'playbook_version', 'model_name')
    list_filter = ('helpful', 'mode', 'playbook_version', 'model_name')
    search_fields = ('question', 'reply', 'comment')
    readonly_fields = ('user', 'helpful', 'mode', 'question', 'reply', 'comment', 'playbook_version', 'model_name', 'created_at')

    @admin.display(description='Question')
    def short_question(self, obj):
        return obj.question[:80]


@admin.register(CoachMemory)
class CoachMemoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'note', 'created_at')
    search_fields = ('note', 'user__username')
