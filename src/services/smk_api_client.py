import requests


class SMKAPIClient:
    BASE_URL = "https://api.smk.dk/api/v1/art/"

    def get_thumbnail_url(self, object_number: str) -> str:
        """Fetch the thumbnail URL for a given object number."""
        url = f"{self.BASE_URL}?object_number={object_number}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data['items'][0]['image_thumbnail']
