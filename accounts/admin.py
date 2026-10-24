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
        'username', 'email', 'get_department', 'get_online', 'get_last_seen', 'last_login',
        'date_joined', 'is_staff', 'get_login_count'
    ]
    list_select_related = ['profile', 'presence']
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

    def get_online(self, obj):
        return is_online(getattr(obj, 'presence', None))
    get_online.short_description = 'Online'
    get_online.boolean = True

    def get_last_seen(self, obj):
        presence = getattr(obj, 'presence', None)
        return presence.last_seen if presence else None
    get_last_seen.short_description = 'Last seen'
    get_last_seen.admin_order_field = 'presence__last_seen'

    def changelist_view(self, request, extra_context=None):
        """Add online / active user stats (based on real activity, not just logins)."""
        extra_context = extra_context or {}
        extra_context.update({
            'online_now': online_users().count(),
            'active_users_today': active_user_count(1),
            'active_users_7d': active_user_count(7),
            'active_users_30d': active_user_count(30),
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


@admin.register(UserPresence)
class UserPresenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'last_seen', 'get_online']
    search_fields = ['user__username', 'user__email']
    ordering = ['-last_seen']
    readonly_fields = ['user', 'last_seen']

    def get_online(self, obj):
        return is_online(obj)
    get_online.short_description = 'Online'
    get_online.boolean = True

    def has_add_permission(self, request):
        return False


@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    list_display = ['date', 'user']
    list_filter = ['date']
    search_fields = ['user__username']
    date_hierarchy = 'date'
    readonly_fields = ['user', 'date']

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
