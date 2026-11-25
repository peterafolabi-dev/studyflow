from .presence import touch_presence


class UserPresenceMiddleware:
    """Refresh authenticated users' last-seen timestamp (and today's activity) at most once a minute."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            touch_presence(user)
        return response


class PermissionsPolicyMiddleware:
    """Tell browsers this site never needs location, payment or USB access (camera/mic stay allowed for voice and gestures)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', 'geolocation=(), payment=(), usb=(), interest-cohort=()')
        return response
