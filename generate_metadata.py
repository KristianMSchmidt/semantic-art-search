import requests
import csv
import os
import sys
from urllib.parse import urlencode
from typing import Any, Dict, List


def check_file_exists(file_path: str) -> None:
    """Check if a file exists and prompt the user to overwrite it."""
    if os.path.exists(file_path):
        print(f"Warning: The file '{file_path}' already exists.")
        print("If you continue, the file will be overwritten.")
        response = input("Do you want to continue? (y/n): ")
        if response.lower() != "y":
            print("Exiting script.")
            sys.exit()


def fetch_data(api_url: str) -> Dict[str, Any]:
    """Fetch data from the API and return it as JSON."""
    response = requests.get(api_url)
    response.raise_for_status()  # Raise an error for HTTP issues
    return response.json()


def write_metadata(csv_file: str, metadata: List[List[Any]]) -> None:
    """Write metadata to a CSV file."""
    with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        # Write header
        writer.writerow(
            [
                "object_number",
                "title",
                "object_name",
                "artist",
                "year_start",
                "year_end",
                "thumbnail_url",
                "image_path",  # Initially empty
                "download_status",  # Initially "pending"
            ]
        )
        writer.writerows(metadata)


def process_items(data: Dict[str, Any]) -> List[List[Any]]:
    """Process items from API data and return a list of metadata."""
    metadata = []
    for item in data.get('items', []):
        try:
            metadata.append(
                [
                    item['object_number'],
                    item.get("titles", [{}])[0].get("title", "Unknown"),
                    item.get("object_names", [{}])[0].get("name", "Unknown"),
                    item.get("artist", ["Unknown"])[0],
                    item.get("production_date", [{}])[0]
                    .get("start", "Unknown")
                    .split("-")[0],
                    item.get("production_date", [{}])[0]
                    .get("end", "Unknown")
                    .split("-")[0],
                    item['image_thumbnail'],
                    "",  # image_path initially empty
                    "pending",  # download_status initially "pending"
                ]
            )
        except KeyError as e:
            print(f"Missing key in item: {e}")
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
    ]
    START_DATE = "1800-01-01T00:00:00.000Z"
    END_DATE = "1899-12-31T23:59:59.999Z"
    QUERY_PARAMS = {
        "keys": "*",
        "fields": ",".join(FIELDS),
        "filters": "[has_image:true],[object_names:maleri]",
        "range": f"[production_dates_end:{{{START_DATE};{END_DATE}}}]",
        "offset": 0,
        "rows": 2000,  # Max is 2000
    }
    CSV_FILE = "data/metadata.csv"

    # Check if the metadata file already exists
    check_file_exists(CSV_FILE)

    print("Fetching data from the API...")
    offset = 0
    all_metadata = []
    while True:
        QUERY_PARAMS['offset'] = offset
        API_URL = f"{BASE_URL}?{urlencode(QUERY_PARAMS)}"
        data = fetch_data(API_URL)

        # Check if there are any items in the response
        if not data.get('items'):
            break

        # Process and accumulate metadata
        print(f"Processing items for offset {offset}...")
        all_metadata.extend(process_items(data))

        # Check if we've retrieved all the data
        if offset + QUERY_PARAMS['rows'] >= data['found']:
            break

        # Update offset for the next batch
        offset += QUERY_PARAMS['rows']

    print(f"Total items fetched: {len(all_metadata)}")

    print("Writing metadata to CSV...")
    write_metadata(CSV_FILE, all_metadata)

    print("CSV file created successfully.")


if __name__ == "__main__":
    main()
