from artsearch.src.services.museum_clients.base_client import MuseumAPIClient

# AIC asks API clients to identify themselves with this header (https://api.artic.edu/docs/).
# Since late 2026 their Cloudflare blocks python-requests calls that leave it out (HTTP 403).
AIC_REQUEST_HEADERS = {
    "AIC-User-Agent": "semantic-art-search (kmollerschmidt@gmail.com)",
}


class AICAPIClient(MuseumAPIClient):
    def get_object_url(self, museum_db_id: str) -> str:
        """
        Construct the API URL for an AIC artwork.

        AIC uses the numeric id (not main_reference_number) in URLs.
        Example: https://api.artic.edu/api/v1/artworks/27992
        """
        return f"https://api.artic.edu/api/v1/artworks/{museum_db_id}"

    def get_page_url(self, museum_db_id: str) -> str:
        """
        Construct the public page URL for an AIC artwork.

        AIC uses the numeric id (not main_reference_number) in URLs.
        Example: https://www.artic.edu/artworks/27992
        """
        return f"https://www.artic.edu/artworks/{museum_db_id}"
