from django.http import HttpRequest

from artsearch.src.config import config


def bucket_host(request: HttpRequest) -> dict[str, str]:
    """
    Origin of the image bucket, so base.html can preconnect to it: the browser
    then sets up the connection (DNS + TLS, ~0.15s) while the page and search
    results are still loading, instead of when the first thumbnail is needed.
    Must match the host in get_bucket_image_url.
    """
    return {"bucket_host": f"https://{config.aws_bucket_region}.linodeobjects.com"}


def goatcounter(request: HttpRequest) -> dict[str, str | None]:
    """
    GoatCounter site code for the visitor-stats script in base.html (no cookies,
    no personal data). None when unset, or for logged-in staff, so the owner's
    and the `claude` test user's visits aren't counted.
    """
    # Requests built without the auth middleware (e.g. RequestFactory) have no user
    user = getattr(request, "user", None)
    if user is not None and user.is_staff:
        return {"goatcounter_code": None}
    return {"goatcounter_code": config.goatcounter_code}
