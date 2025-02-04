from artsearch.src.cli.shared.interactive_search import interactive_search
from artsearch.src.global_services import search_service_instance


def search_text(search_service, query):
    """Search for artworks using a text query."""
    return search_service.search_text(query)


def main():
    prompt = "Enter your query (or type 'exit' to quit): "
    interactive_search(search_service_instance, prompt, search_text)


if __name__ == "__main__":
    main()
