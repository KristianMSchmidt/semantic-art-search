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
