from search_service import SearchService
from utils import get_qdrant_client, get_clip_embedder


def interactive_search(search_service: SearchService):
    while True:
        query = input("Enter artwork's object number (or type 'exit' to quit): ")
        if query.lower() == 'exit':
            print("Exiting the program. Goodbye!")
            break
        results = search_service.search_similar_images(query)
        for result in results:
            print("------------")
            print(f"Score: {result['score']}")
            print(f"Title: {result['title']}")
            print(f"Artist: {result['artist']}")
            print(f"Thumbnail: {result['thumbnail_url']}")


def main():
    qdrant_client = get_qdrant_client()
    embedder = get_clip_embedder()
    search_service = SearchService(
        qdrant_client, embedder, collection_name="smk_artworks"
    )
    interactive_search(search_service)


if __name__ == "__main__":
    main()
