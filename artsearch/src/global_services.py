"""
This module is used to initialize the global services used in the application.
It is especially important to have a single instance of the clip_embedder and search_service,
as these rely on the resource-intensive CLIP model.

From anywhere in the code, import the services from this module.
"""

import sys

clip_embedder_instance = None
search_service_instance = None
qdrant_client_instance = None
smk_api_client_instance = None


def initialize_services():
    # Only initialize if the command is not one of the ones that don't need it
    management_commands_to_skip = ['migrate', 'collectstatic', 'shell']
    if len(sys.argv) > 1 and sys.argv[1] in management_commands_to_skip:
        return
    global clip_embedder_instance, search_service_instance, qdrant_client_instance, smk_api_client_instance
    if clip_embedder_instance is None:
        from artsearch.src.services.clip_embedder import CLIPEmbedder
        from artsearch.src.services.qdrant_search_service import QdrantSearchService
        from artsearch.src.services.smk_api_client import SMKAPIClient
        from qdrant_client import QdrantClient
        from artsearch.src.config import Config

        clip_embedder_instance = CLIPEmbedder()
        smk_api_client_instance = SMKAPIClient()
        qdrant_client_instance = QdrantClient(
            url=Config.QDRANT_URL, api_key=Config.QDRANT_API_KEY
        )
        search_service_instance = QdrantSearchService(
            qdrant_client=qdrant_client_instance,
            embedder=clip_embedder_instance,
            smk_api_client=smk_api_client_instance,
            collection_name="smk_artworks",
        )
