from urllib.parse import quote

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from artsearch.models import ArtworkStats


def artwork_page_path(museum_slug: str, object_number: str) -> str:
    """
    Same result as reverse("artwork-page", ...), with the same quoting as
    Django, but much faster: reverse() made a 10k-URL sitemap page take seconds.
    """
    safe = "!$&'()*+,;=/~:@"  # what Django's reverse() leaves unquoted
    return f"/artwork/{quote(museum_slug, safe=safe)}/{quote(object_number, safe=safe)}/"


class StaticSitemap(Sitemap):
    def items(self) -> list[str]:
        return ["home", "art-map"]

    def location(self, item: str) -> str:
        return reverse(item)


class ArtworkSitemap(Sitemap):
    """One URL per artwork page. ArtworkStats mirrors the Qdrant collection."""

    limit = 10000  # URLs per sitemap page (Google allows up to 50,000)

    def items(self):
        return ArtworkStats.objects.order_by("museum_slug", "object_number").values_list(
            "museum_slug", "object_number"
        )

    def location(self, item: tuple[str, str]) -> str:
        return artwork_page_path(*item)


SITEMAPS = {"static": StaticSitemap, "artworks": ArtworkSitemap}
