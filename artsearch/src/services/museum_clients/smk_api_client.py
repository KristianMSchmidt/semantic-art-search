from artsearch.src.services.museum_clients.base_client import MuseumAPIClient


class SMKAPIClient(MuseumAPIClient):
    BASE_URL = "https://api.smk.dk/api/v1/art/"

    def get_object_url(self, object_number: str) -> str:
        return f"{self.BASE_URL}?object_number={object_number}"

    def get_page_url(self, object_number: str) -> str:
        return f"https://open.smk.dk/artwork/image/{object_number}"
