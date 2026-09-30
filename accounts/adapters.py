from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class DebugSocialAccountAdapter(DefaultSocialAccountAdapter):
    """TEMPORARY diagnostic adapter. Re-raises the real exception instead of
    showing allauth's generic 'Third-Party Login Failure' page, so Django's
    own error handling (and our logging) can actually see what broke.
    Remove this file and the SOCIALACCOUNT_ADAPTER setting once the bug
    is found and fixed — always raising like this is wrong for real users.
    """

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        if exception:
            raise exception
        return super().on_authentication_error(request, provider, error, exception, extra_context)
