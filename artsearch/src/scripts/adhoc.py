from qdrant_client import QdrantClient, models
from PIL import Image
import requests
from artsearch.src.services.smk_api_client import SMKAPIClient
from artsearch.src.services.qdrant_service import get_qdrant_service


def test_search():
    qdrant_service = get_qdrant_service()
    qdrant_client = qdrant_service.qdrant_client
    # x = [0.1 for i in range(768)]
    # result = qdrant_service._search(x, 10)

    query_vector = [0.1 for i in range(768)]

    # Filter for points where 'maleri' is in object_names_flattened
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                # key="object_names_flattened", match=models.MatchValue(value="akvarel")
                key="object_names_flattened",
                match=models.MatchAny(any=["akvarel", "grafik"]),
            )
        ]
    )
    hits = qdrant_client.search(
        collection_name="smk_artworks_dev_l_14",
        query_vector=query_vector,
        limit=10,
        offset=0,
        query_filter=query_filter,
    )


def make_favicon():
    # Initialize the SMK API client
    smk_client = SMKAPIClient()

    # Get the thumbnail URL for the specified artwork
    object_number = "KMSr171"
    thumbnail_url = smk_client.get_thumbnail_url(object_number)

    # Fetch the image from the URL
    response = requests.get(thumbnail_url, stream=True)
    response.raise_for_status()  # Ensure we got a valid response

    # Open the image
    img = Image.open(response.raw)  # type: ignore

    # Resize image to favicon size (typically 32x32 or 48x48)
    favicon_size = (32, 32)  # You can adjust to (16,16) or (48,48) if needed
    img = img.resize(favicon_size, Image.LANCZOS)  # type: ignore

    # Save the image as favicon.ico
    img.save("artsearch/static/favicon.ico", format="ICO")

    print("Favicon saved as favicon.ico")


if "__main__" == "__main__":
    test_search()
    pass
    # make_favicon()
