import csv
import os
from PIL import Image
from io import BytesIO
import requests


def download_image(image_url: str, save_dir: str, object_number: str) -> str:
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


def process_csv(csv_file: str, save_dir: str) -> None:
    """Read the metadata CSV, download images, and update the CSV with results."""
    temp_file = csv_file + ".tmp"

    with open(csv_file, mode="r", newline="", encoding="utf-8") as infile, open(
        temp_file, mode="w", newline="", encoding="utf-8"
    ) as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            try:
                if row["download_status"] == "success":
                    # Skip already downloaded images
                    writer.writerow(row)
                    continue

                print(f"Downloading image for object: {row['object_number']}")
                image_path = download_image(
                    row["thumbnail_url"], save_dir, row["object_number"]
                )
                row["image_path"] = image_path
                row["download_status"] = "success"
            except Exception as e:
                print(f"Error downloading image for {row['object_number']}: {e}")
                row["download_status"] = "error"

            writer.writerow(row)

    # Replace old CSV with updated CSV
    os.replace(temp_file, csv_file)


def main():
    SAVE_DIR = "data/images"
    CSV_FILE = "data/metadata.csv"

    # Ensure save directory exists
    os.makedirs(SAVE_DIR, exist_ok=True)

    print("Reading metadata CSV and downloading images...")
    process_csv(CSV_FILE, SAVE_DIR)

    print("Image downloading completed.")


if __name__ == "__main__":
    main()
