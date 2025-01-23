from src.services.qdrant_search_service import QdrantSearchService
from src.services.smk_api_client import SMKAPIClient
from src.utils import get_qdrant_client, get_clip_embedder


def interactive_search(search_service: QdrantSearchService):
    while True:
        object_number = input(
            "Enter artwork's object number (or type 'exit' to quit): "
        )
        if object_number.lower() == 'exit':
            print("Exiting the program. Goodbye!")
            break
        results = search_service.search_similar_images(object_number)
        for result in results:
            print("------------")
            print(f"Score: {result['score']}")
            print(f"Title: {result['title']}")
            print(f"Artist: {result['artist']}")
            print(f"Thumbnail: {result['thumbnail_url']}")


def main():
    qdrant_client = get_qdrant_client()
    embedder = get_clip_embedder()
    smk_api_client = SMKAPIClient()
    search_service = QdrantSearchService(
        qdrant_client, embedder, smk_api_client, collection_name="smk_artworks"
    )
    interactive_search(search_service)


if __name__ == "__main__":
    main()
