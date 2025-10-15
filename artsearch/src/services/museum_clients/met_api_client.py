from artsearch.src.services.museum_clients.base_client import MuseumAPIClient


class METAPIClient(MuseumAPIClient):
    BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
    OBJECTS_URL = f"{BASE_URL}/objects"

    def get_object_url(self, museum_db_id: int) -> str:
        """
        For MET, we use museum_db_id (objectID) instead of object_number (accessionNumber).
        The object_number parameter name is kept for interface consistency.
        """
        return f"{self.OBJECTS_URL}/{museum_db_id}"
