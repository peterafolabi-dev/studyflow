from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils import timezone

from .models import LoginRecord, Notification, Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Academic Profile'


class LoginRecordInline(admin.TabularInline):
    model = LoginRecord
    extra = 0
    readonly_fields = ['timestamp', 'login_method', 'ip_address', 'user_agent']
    can_delete = False
    max_num = 10
    ordering = ['-timestamp']

    def has_add_permission(self, request, obj=None):
        return False


class CustomUserAdmin(BaseUserAdmin):
    inlines = [ProfileInline, LoginRecordInline]
    list_display = [
        'username', 'email', 'get_department', 'last_login', 'date_joined',
        'is_staff', 'get_login_count'
    ]
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'date_joined', 'last_login']
    search_fields = ['username', 'email', 'profile__department']
    ordering = ['-last_login']
    change_list_template = 'admin/accounts/user/change_list.html'

    def get_department(self, obj):
        if hasattr(obj, 'profile') and obj.profile.department:
            return obj.profile.department
        return '-'
    get_department.short_description = 'Department'

    def get_login_count(self, obj):
        return obj.login_records.count()
    get_login_count.short_description = 'Total Logins'

    def changelist_view(self, request, extra_context=None):
        """Add active user stats to the admin dashboard."""
        extra_context = extra_context or {}
        now = timezone.now()

        extra_context.update({
            'active_users_today': User.objects.filter(
                login_records__timestamp__date=now.date()
            ).distinct().count(),
            'active_users_7d': User.objects.filter(
                login_records__timestamp__gte=now - timedelta(days=7)
            ).distinct().count(),
            'active_users_30d': User.objects.filter(
                login_records__timestamp__gte=now - timedelta(days=30)
            ).distinct().count(),
            'total_users': User.objects.filter(is_active=True).count(),
        })

        return super().changelist_view(request, extra_context=extra_context)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(LoginRecord)
class LoginRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'timestamp', 'login_method', 'ip_address', 'user_agent']
    list_filter = ['login_method', 'timestamp']
    search_fields = ['user__username', 'user__email', 'ip_address']
    readonly_fields = ['user', 'timestamp', 'ip_address', 'user_agent', 'login_method']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    def has_add_permission(self, request):
        return False


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'level', 'reading_goal']
    search_fields = ['user__username', 'department']
    list_filter = ['level']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'message', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'message']
