from artsearch.src.services.museum_clients.base_client import MuseumAPIClient


class CMAAPIClient(MuseumAPIClient):
    BASE_URL = "https://openaccess-api.clevelandart.org/api/artworks/"

    def get_object_url(self, object_number: str) -> str:
        return f"{self.BASE_URL}?accession_number={object_number}"
