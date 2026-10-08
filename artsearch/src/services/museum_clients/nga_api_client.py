from artsearch.src.services.museum_clients.base_client import MuseumAPIClient


class NGAAPIClient(MuseumAPIClient):
    def get_object_url(self, museum_db_id: str) -> str:
        """
        NGA has no per-object metadata API (its data is published as CSV files on
        GitHub), so we point to the artwork's public page, which shows its metadata.
        """
        return self.get_page_url(museum_db_id)

    def get_page_url(self, museum_db_id: str) -> str:
        """
        Construct the public page URL for an NGA artwork.

        NGA uses the numeric objectid (not the accession number) in URLs.
        Example: https://www.nga.gov/collection/art-object-page.46482.html
        """
        return f"https://www.nga.gov/collection/art-object-page.{museum_db_id}.html"
