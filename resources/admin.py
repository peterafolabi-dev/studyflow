from django.contrib import admin

from .models import Loan, PhysicalHolding, Resource, ResourceComment, ResourceReport


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'resource_type', 'course_code', 'uploaded_by', 'download_count', 'created_at')
    list_filter = ('resource_type', 'course_code')
    search_fields = ('title', 'course_code', 'description')
    actions = ['delete_missing_files']

    @admin.action(description='Delete selected entries whose file is missing from storage')
    def delete_missing_files(self, request, queryset):
        gone = [r for r in queryset if r.file and not r.file_available()]
        names = ', '.join(r.title for r in gone[:5])
        count = len(gone)
        for r in gone:
            r.delete()
        self.message_user(request, f'Deleted {count} entr{"y" if count == 1 else "ies"} with missing files. {names}'.strip())


@admin.register(PhysicalHolding)
class PhysicalHoldingAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'shelf_location', 'is_available')
    list_filter = ('category', 'is_available')
    search_fields = ('title', 'author')


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('user', 'holding', 'borrowed_at', 'due_at', 'returned_at')
    list_filter = ('returned_at',)
    search_fields = ('user__username', 'holding__title')


@admin.register(ResourceComment)
class ResourceCommentAdmin(admin.ModelAdmin):
    list_display = ('resource', 'user', 'created_at')
    search_fields = ('body', 'user__username')


@admin.register(ResourceReport)
class ResourceReportAdmin(admin.ModelAdmin):
    list_display = ('resource', 'reason', 'reporter', 'reviewed', 'created_at')
    list_filter = ('reason', 'reviewed', 'created_at')
    search_fields = ('resource__title', 'reporter__username', 'detail')
    raw_id_fields = ('resource', 'reporter')
    actions = ['mark_reviewed']

    @admin.action(description='Mark selected reports as reviewed')
    def mark_reviewed(self, request, queryset):
        queryset.update(reviewed=True)
