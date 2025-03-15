import requests

# Hvor mange malerier er der?


def print_openaccess_results(keyword, skip=0, limit=100):
    url = "https://openaccess-api.clevelandart.org/api/artworks"
    params = {
        "q": keyword,
        "skip": skip,
        "limit": limit,
        "has_image": 1,
        # "type": "Painting",
        "cc0": 1,
    }

    r = requests.get(url, params=params)
    # print resulting url
    print(r.url)
    data = r.json()

    print()
    print(data["info"])
    print()

    for artwork in data["data"]:
        licence = artwork["share_license_status"]

        object_number = artwork["accession_number"]
        title = artwork["title"]  # english title
        artist = artwork["creators"]
        image = artwork["images"]["web"]["url"]
        type = artwork["type"]
        production_date_start = artwork["creation_date_earliest"]
        production_date_end = artwork["creation_date_latest"]

        # print(f"object_number: {object_number}")
        # print(f"title: {title}")
        # print(f"artist: {artist[0]['description'].split('(')[0].strip()}")
        # print(f"image: {image}")
        # print(f"type: {type}")
        # print(f"production_date_start: {production_date_start}")
        # print(f"production_date_end: {production_date_end}")
        print(f"licence: {licence}")
        # print("\n")


if __name__ == "__main__":
    print_openaccess_results("", 0, 1)
