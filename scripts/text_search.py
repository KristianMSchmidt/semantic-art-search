from scripts.shared.interactive_search import interactive_search
from scripts.shared.search_config import initialize_search_service


def search_text(search_service, query):
    """Search for artworks using a text query."""
    return search_service.search_text(query)


def main():
    search_service = initialize_search_service()
    prompt = "Enter your query (or type 'exit' to quit): "
    interactive_search(search_service, prompt, search_text)


if __name__ == "__main__":
    main()
