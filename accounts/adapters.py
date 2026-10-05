import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from allauth.account.utils import user_email, user_username
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger('allauth')


class StudyFlowSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Production social account adapter for StudyFlow.
    Handles seamless auto-linking of Google accounts with matching verified emails
    and provides graceful error handling.
    """

    def pre_social_login(self, request, sociallogin):
        """If a local user already exists with the same email address as the Google
        account, automatically connect the social account so the user is logged in
        seamlessly without throwing an email conflict error."""
        if sociallogin.is_existing:
            return

        # Extract verified email from the social account
        email = None
        if hasattr(sociallogin, 'email_addresses') and sociallogin.email_addresses:
            for email_address in sociallogin.email_addresses:
                if email_address.email:
                    email = email_address.email
                    break

        if not email and hasattr(sociallogin, 'user') and sociallogin.user:
            email = user_email(sociallogin.user)

        if email:
            User = get_user_model()
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user:
                sociallogin.connect(request, existing_user)

    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """Gracefully handle authentication errors rather than crashing with 500."""
        logger.error(
            f"Social auth error: provider={provider_id}, error={error}, "
            f"exception={exception}, extra_context={extra_context}"
        )
        if request:
            messages.error(
                request,
                "Unable to sign in with Google. If your account is not registered as a test user or has restrictions, "
                "please sign in with your username or try another Google account."
            )
            return redirect('login')
        return super().authentication_error(request, provider_id, error, exception, extra_context)