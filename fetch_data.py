import requests
import sys
import os
import csv
from PIL import Image
from io import BytesIO
from urllib.parse import urlencode
from typing import Any, Dict


def check_file_exists(file_path: str) -> None:
    """Check if a file exists and exit the script if it does."""
    if os.path.exists(file_path):
        print(f"Error: The file '{file_path}' already exists.")
        print("Please delete the file manually if you want to rerun the script.")
        sys.exit(1)  # Exit the script with an error code


def fetch_data(api_url: str) -> Dict[str, Any]:
    """Fetch data from the API and return it as JSON."""
    response = requests.get(api_url)
    response.raise_for_status()  # Raise an error for HTTP issues
    return response.json()


def save_image(image_url: str, save_dir: str, object_number: str) -> str:
    """Download and save an image locally."""
    filename = os.path.join(save_dir, f"{object_number}.jpg")
    if os.path.exists(filename):
        print(f"Image {filename} already exists. Skipping download.")
        return filename
    response = requests.get(image_url)
    response.raise_for_status()
    img = Image.open(BytesIO(response.content))
    img.save(filename)
    return filename


def write_metadata(csv_file: str, metadata: list) -> None:
    """Write metadata to a CSV file."""
    with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        # Write header
        writer.writerow(
            [
                "image_path",
                "object_number",
                "title",
                "object_name",  # fx. maleri
                "artist",
                "year_start",
                "year_end",
                "thumbnail_path",
            ]
        )
        writer.writerows(metadata)


def process_items(data: Dict[str, Any], save_dir: str) -> list:
    """Process items from API data and return a list of metadata."""
    metadata = []
    for count, item in enumerate(data.get('items', []), start=1):
        try:
            image_url = item['image_thumbnail']
            object_number = item['object_number']
            image_path = save_image(image_url, save_dir, object_number)

            metadata.append(
                [
                    image_path,
                    object_number,
                    item.get("titles", [{}])[0].get("title", "Unknown"),
                    item.get("object_names", [{}])[0].get("name", "Unknown"),
                    item.get("artist", ["Unknown"])[0],
                    item.get("production_date", [{}])[0]
                    .get("start", "Unknown")
                    .split("-")[0],
                    item.get("production_date", [{}])[0]
                    .get("end", "Unknown")
                    .split("-")[0],
                    image_url,
                ]
            )

            if count % 10 == 0:
                print(f"Processed {count} items")
        except Exception as e:
            print(f"Error processing item {item.get('id', 'Unknown')}: {e}")
    return metadata


def main():
    BASE_URL = "https://api.smk.dk/api/v1/art/search/"
    FIELDS = [
        "titles",
        "artist",
        "object_names",
        "production_date",
        "object_number",
        "image_thumbnail",
        "object_names",
    ]
    QUERY_PARAMS = {
        "keys": "*",
        "fields": ",".join(FIELDS),
        "filters": "[has_image:true],[object_names:maleri],[public_domain:true]",
        "offset": 0,
        "rows": 500,
    }

    API_URL = f"{BASE_URL}?{urlencode(QUERY_PARAMS)}"
    SAVE_DIR = "data/images"
    CSV_FILE = "data/meta_data.csv"

    # Check if the metadata file already exists
    check_file_exists(CSV_FILE)

    # Ensure save directory exists
    os.makedirs(SAVE_DIR, exist_ok=True)

    print("Fetching data from the API...")
    data = fetch_data(API_URL)

    print("Processing items and downloading images...")
    metadata = process_items(data, SAVE_DIR)

    print("Writing metadata to CSV...")
    write_metadata(CSV_FILE, metadata)

    print("Script completed successfully.")


if __name__ == "__main__":
    print("This script will fetch images from the SMK API and save them locally.")
    print("Do you want to continue? (y/n)")
    response = input().strip().lower()
    if response == "y":
        main()
    else:
        print("Script execution cancelled.")
