from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def is_safe_url(request, url):
    """True only for URLs that stay on this site, so redirects can't be used for phishing."""
    return bool(url) and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )


def redirect_next(request, fallback, url=None):
    """Redirect to `url` (default: the request's `next` value) if it is local, else to `fallback`."""
    if url is None:
        url = request.POST.get('next') or request.GET.get('next') or ''
    return redirect(url if is_safe_url(request, url) else fallback)


def redirect_back(request, fallback):
    """Redirect to the referring page if it is local, else to `fallback`."""
    return redirect_next(request, fallback, url=request.META.get('HTTP_REFERER', ''))


def int_or(value, default):
    """Parse a form value as int, falling back instead of raising a 500."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
