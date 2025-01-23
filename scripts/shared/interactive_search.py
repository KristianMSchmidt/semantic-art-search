def interactive_search(search_service, prompt, search_function):
    """
    Generic interactive search function.

    Args:
        search_service: An instance of QdrantSearchService.
        prompt: Input prompt message.
        search_function: Function to perform the specific search.
    """
    while True:
        query = input(prompt)
        if query.lower() == 'exit':
            print("Exiting the program. Goodbye!")
            break

        print("\n" + "=" * 50)
        print(f" Results for: '{query}' ".center(50, "="))
        print("=" * 50)

        results = search_function(search_service, query)
        for result in results:
            print("------------")
            print(f"Score: {result['score']}")
            print(f"Title: {result['title']}")
            print(f"Artist: {result['artist']}")
            print(f"Thumbnail: {result['thumbnail_url']}")
