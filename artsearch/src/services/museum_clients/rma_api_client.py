from artsearch.src.services.museum_clients.base_client import MuseumAPIClient


class RMAAPIClient(MuseumAPIClient):
    BASE_URL = "https://data.rijksmuseum.nl/oai?verb=GetRecord&metadataPrefix=edm&identifier=https://id.rijksmuseum.nl"

    def get_object_url(self, museum_db_id: str) -> str:
        """
        For RMA, we use museum_db_id (item_id) instead of object_number.
        The object_number parameter name is kept for interface consistency.
        """
        return f"{self.BASE_URL}/{museum_db_id}"
