from artsearch.src.services.museum_clients.base_client import MuseumAPIClient


class FNGAPIClient(MuseumAPIClient):
    def get_object_url(self, museum_db_id: str) -> str:
        """
        The Finnish National Gallery's per-object search API needs an API key, and
        its open data is a full collection dump, so we point to the artwork's public
        page, which shows its metadata.
        """
        return self.get_page_url(museum_db_id)

    def get_page_url(self, museum_db_id: str) -> str:
        """
        Construct the public page URL for a Finnish National Gallery artwork.

        Uses the numeric objectId (not the inventory number).
        Example: https://kokoelma.kansallisgalleria.fi/en/object/408013
        """
        return f"https://kokoelma.kansallisgalleria.fi/en/object/{museum_db_id}"
