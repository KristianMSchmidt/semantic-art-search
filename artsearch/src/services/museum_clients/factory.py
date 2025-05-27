from artsearch.src.services.museum_clients.smk_api_client import SMKAPIClient
from artsearch.src.services.museum_clients.cma_api_client import CMAAPIClient
from artsearch.src.services.museum_clients.rma_api_client import RMAAPIClient
from artsearch.src.services.museum_clients.base_client import MuseumAPIClient

CLIENTS = {
    "smk": SMKAPIClient,
    "cma": CMAAPIClient,
    "rma": RMAAPIClient,
}


def get_museum_client(museum_name: str) -> MuseumAPIClient:
    client_class = CLIENTS.get(museum_name)
    if not client_class:
        raise ValueError(f"Unknown museum client: {museum_name}")
    return client_class()
