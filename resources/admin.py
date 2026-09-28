from django.contrib import admin

from .models import Loan, PhysicalHolding, Resource, ResourceComment


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'resource_type', 'course_code', 'uploaded_by', 'download_count', 'created_at')
    list_filter = ('resource_type', 'course_code')
    search_fields = ('title', 'course_code', 'description')


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
