from django.contrib import admin
from .models import (
    StudySpot, PowerVote, CourseNotice, LodgeReview, RoommateProfile,
    SIWESCompany, SIWESLogEntry, MarketplaceItem, EmergencyContact
)

@admin.register(StudySpot)
class StudySpotAdmin(admin.ModelAdmin):
    list_display = ('name', 'campus', 'current_status', 'last_reported_at')
    list_filter = ('campus', 'current_status')
    search_fields = ('name', 'location_desc')

@admin.register(CourseNotice)
class CourseNoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'course_code', 'department', 'level', 'urgency', 'is_pinned', 'created_at')
    list_filter = ('urgency', 'level', 'is_pinned')
    search_fields = ('title', 'course_code', 'department', 'body')

@admin.register(LodgeReview)
class LodgeReviewAdmin(admin.ModelAdmin):
    list_display = ('lodge_name', 'area', 'rent_estimate', 'reviewer', 'created_at')
    list_filter = ('area',)
    search_fields = ('lodge_name', 'review_text')

@admin.register(RoommateProfile)
class RoommateProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'level', 'budget_range', 'preferred_area', 'is_active')
    list_filter = ('level', 'is_active')

@admin.register(SIWESCompany)
class SIWESCompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'state', 'industry', 'takes_it_students')
    list_filter = ('state', 'industry', 'takes_it_students')
    search_fields = ('name', 'city', 'industry')

@admin.register(SIWESLogEntry)
class SIWESLogEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'week_number', 'date', 'department_unit')
    list_filter = ('week_number', 'date')

@admin.register(MarketplaceItem)
class MarketplaceItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'is_free', 'condition', 'seller', 'is_sold', 'created_at')
    list_filter = ('category', 'is_free', 'condition', 'is_sold')
    search_fields = ('title', 'description')

@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'phone_number', 'campus')
    list_filter = ('category', 'campus')



from .models import CampusEvent, LostFoundItem, Opportunity  # noqa: E402


@admin.register(LostFoundItem)
class LostFoundItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'location', 'reporter', 'is_resolved', 'created_at')
    list_filter = ('kind', 'is_resolved')
    search_fields = ('title', 'description', 'location')


@admin.register(CampusEvent)
class CampusEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'starts_at', 'location', 'organizer', 'is_approved')
    list_filter = ('is_approved',)
    search_fields = ('title', 'description', 'location')
    actions = ['approve']

    @admin.action(description='Approve selected events')
    def approve(self, request, queryset):
        self.message_user(request, f'{queryset.update(is_approved=True)} event(s) approved.')


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'organisation', 'deadline', 'submitted_by', 'is_approved')
    list_filter = ('kind', 'is_approved')
    search_fields = ('title', 'organisation', 'description')
    actions = ['approve']

    @admin.action(description='Approve selected opportunities')
    def approve(self, request, queryset):
        self.message_user(request, f'{queryset.update(is_approved=True)} opportunity(ies) approved.')
