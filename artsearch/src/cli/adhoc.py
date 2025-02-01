from artsearch.src.cli.shared.interactive_search import interactive_search
from artsearch.src.services.search_service import search_service
from PIL import Image
import requests
from artsearch.src.services.smk_api_client import SMKAPIClient


def make_favicon():
    # Initialize the SMK API client
    smk_client = SMKAPIClient()

    # Get the thumbnail URL for the specified artwork
    object_number = 'KMSr171'
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
    make_favicon()
