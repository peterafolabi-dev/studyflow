from django.http import HttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class DebugSocialAccountAdapter(DefaultSocialAccountAdapter):
    """TEMPORARY diagnostic adapter — shows the real reason allauth rejected
    a social login, instead of its generic error page. Remove this file and
    the SOCIALACCOUNT_ADAPTER setting once the bug is found and fixed."""

    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        if exception:
            raise exception
        return HttpResponse(
            f"<pre>provider_id: {provider_id!r}\nerror: {error!r}\n"
            f"extra_context: {extra_context!r}\n"
            f"session keys: {list(request.session.keys())!r}</pre>",
            status=200,
        )