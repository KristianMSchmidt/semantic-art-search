"""
Script to discover the distribution of public domain artworks with images across artwork types.

Usage:
    python etl/scripts/discover_aic_artwork_type_distribution.py
"""

import json
import os
import requests
import time


def get_artwork_types(session: requests.Session) -> dict[int, str]:
    """Fetch all artwork types from the AIC API."""
    base_url = "https://api.artic.edu/api/v1/artwork-types"
    artwork_types = {}
    page = 1

    print("Fetching artwork types from AIC API...")

    while True:
        params = {
            "limit": 100,  # Maximum per page
            "page": page,
            "fields": "id,title"
        }

        response = session.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        # Add artwork types to the dictionary
        for artwork_type in data.get("data", []):
            artwork_types[artwork_type["id"]] = artwork_type["title"]

        # Check if there are more pages
        pagination = data.get("pagination", {})
        if page >= pagination.get("total_pages", 1):
            break

        page += 1
        time.sleep(0.5)  # Be polite to the API

    print(f"Found {len(artwork_types)} artwork types\n")
    return artwork_types


def get_count_for_artwork_type(type_id: int, session: requests.Session) -> int:
    """Get count of public domain artworks with images for a given artwork type."""
    base_url = "https://api.artic.edu/api/v1/artworks/search"

    query = {
        "query[bool][filter][0][term][is_public_domain]": "true",
        "query[bool][filter][1][exists][field]": "image_id",
        "query[bool][filter][2][term][artwork_type_id]": type_id,
        "limit": 1,  # We only need the count, not the actual data
        "page": 1,
    }

    response = session.get(base_url, params=query)
    response.raise_for_status()
    data = response.json()

    return data.get("pagination", {}).get("total", 0)


def main():
    session = requests.Session()

    # Fetch artwork types from the API
    artwork_type_mapping = get_artwork_types(session)

    print("Fetching artwork counts by type (public domain + has image_id)...")
    print("This may take a minute...\n")

    results = {}
    total_count = 0

    for type_id, type_name in sorted(artwork_type_mapping.items()):
        try:
            count = get_count_for_artwork_type(type_id, session)
            results[type_id] = {
                "type_name": type_name,
                "count": count
            }
            total_count += count
            print(f"Type {type_id:2d}: {type_name:30s} = {count:6d} artworks")
            time.sleep(0.5)  # Be polite to the API
        except Exception as e:
            print(f"❌ Type {type_id:2d}: {type_name:30s} - Error: {e}")

    print("\n" + "=" * 70)
    print(f"Total artworks across all types: {total_count}")
    print("=" * 70)

    # Save results to JSON file in the same folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "aic_artwork_type_distribution.json")

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Results saved to: {output_file}")


if __name__ == "__main__":
    main()
