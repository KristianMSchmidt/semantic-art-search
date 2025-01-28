from artsearch.src.cli.shared.interactive_search import interactive_search
from artsearch.src.utils.search_config import initialize_search_service


def search_similar_images(search_service, object_number):
    """Search for similar images based on an object number."""
    return search_service.search_similar_images(object_number)


def main():
    search_service = initialize_search_service()
    prompt = "Enter artwork's object number (or type 'exit' to quit): "
    interactive_search(search_service, prompt, search_similar_images)


if __name__ == "__main__":
    main()
