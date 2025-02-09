import umap
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
import requests
from io import BytesIO
from artsearch.src.services.qdrant_service import get_qdrant_service

# Initialize Qdrant service
qdrant_service = get_qdrant_service()
qdrant_client = qdrant_service.qdrant_client

# Define the collection name to fetch data from
COLLECTION_NAME = "smk_artworks_50d"


# Step 1: Fetch data from Qdrant
print(f"Fetching data from the '{COLLECTION_NAME}' collection...")
all_points, _ = qdrant_client.scroll(
    collection_name=COLLECTION_NAME, scroll_filter=None, with_vectors=True, limit=10_000
)

# Extract vectors and metadata
vectors = []
annotations = []
thumbnails = []
for point in all_points:
    vectors.append(point.vector)

    # Cast payload to a dictionary
    payload = dict(point.payload)

    # Extract metadata fields safely
    artist = payload.get("artist", ["Unknown"])[0] if "artist" in payload else "Unknown"
    titles = payload.get("titles", [])
    title = titles[0].get("title", "Unknown") if titles else "Unknown"
    thumbnail_url = payload.get("thumbnail_url", None)  # None if no URL available

    # Store annotations and thumbnail URLs
    annotations.append(f"Artist: {artist}\nTitle: {title}")
    thumbnails.append(thumbnail_url)

vectors = np.array(vectors)  # Convert to NumPy array

# Step 2: Reduce dimensionality with UMAP
print("Reducing dimensionality for visualization...")
umap_2d = umap.UMAP(n_components=2, metric="euclidean", random_state=42)
vectors_2d = umap_2d.fit_transform(vectors)  # Reduce from 50D to 2D

# Step 3: Highlight selected artists
highlight_artists = ["Vilhelm Lundstrøm", "C.W. Eckersberg", "Henri Matisse"]
highlight_colors = ["red", "orange", "lime"]  # Colors for highlighted artists
default_color = "lightgray"  # Lighter color for non-highlighted points

# Create a color mapping
color_map = {
    artist: color for artist, color in zip(highlight_artists, highlight_colors)
}
point_colors = [
    color_map.get(dict(point.payload).get("artist", ["Unknown"])[0], default_color)  # type: ignore
    for point in all_points
]

# Assign sizes: Larger for highlighted points, smaller for others
highlight_size = 80
default_size = 2
point_sizes = [
    (
        highlight_size
        if dict(point.payload).get("artist", ["Unknown"])[0] in highlight_artists  # type: ignore
        else default_size
    )
    for point in all_points
]

# Step 4: Scatter plot visualization
plt.figure(figsize=(21, 15))  # Bigger plot size
scatter = plt.scatter(
    vectors_2d[:, 0],  # type: ignore
    vectors_2d[:, 1],  # type: ignore
    c=point_colors,
    s=point_sizes,
    alpha=0.6,
    edgecolors="k" if highlight_artists else None,  # Black edges for highlighted points
    linewidth=0.5,
)


# Step 5: Add hover functionality to display images and annotations
def fetch_image(url):
    """Fetch an image from a URL and return it as a PIL Image."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None


annot = plt.gca().annotate(
    "",
    xy=(0, 0),
    xytext=(15, 15),
    textcoords="offset points",
    bbox=dict(boxstyle="round", fc="w"),
    fontsize=12,  # Bigger annotation text
    arrowprops=dict(arrowstyle="->"),
)
annot.set_visible(False)

image_box = None  # Placeholder for the image


def update_annot(ind):
    """Update the annotation and image box when hovering."""
    index = ind["ind"][0]
    pos = scatter.get_offsets()[index]
    annot.xy = pos
    annot.set_text(annotations[index])  # Show metadata

    global image_box
    # Remove the previous image box if it exists
    if image_box is not None and image_box in plt.gca().artists:
        image_box.remove()
        image_box = None

    # Add the new image box
    if thumbnails[index]:
        img = fetch_image(thumbnails[index])
        if img:
            # Resize image for better visibility
            img.thumbnail((200, 200))  # Increase thumbnail size
            image = OffsetImage(img, zoom=1.2)  # Adjust zoom for larger display
            # Offset the image below the scatter point (or adjust based on preference)
            image_box = AnnotationBbox(
                image,
                (pos[0], pos[1] - 1),  # Position slightly below the point
                frameon=True,
                pad=0.3,
                bboxprops=dict(edgecolor="black"),
            )
            plt.gca().add_artist(image_box)


def hover(event):
    """Callback function for hovering."""
    vis = annot.get_visible()
    if event.inaxes == scatter.axes:
        cont, ind = scatter.contains(event)
        if cont:
            update_annot(ind)
            annot.set_visible(True)
            plt.gcf().canvas.draw_idle()
        else:
            if vis:
                annot.set_visible(False)
                global image_box
                if image_box is not None and image_box in plt.gca().artists:
                    image_box.remove()
                    image_box = None
                plt.gcf().canvas.draw_idle()


# Connect hover functionality
plt.gcf().canvas.mpl_connect("motion_notify_event", hover)

# Step 6: Add legend manually
for artist, color in color_map.items():
    plt.scatter(
        [], [], c=color, s=highlight_size, label=artist
    )  # Invisible points for legend

plt.legend(loc="upper right", title="Highlighted Artists", fontsize="large")

plt.title("2D UMAP Projection with Hover Annotations and Image", fontsize=16)
plt.xlabel("UMAP Dimension 1", fontsize=12)
plt.ylabel("UMAP Dimension 2", fontsize=12)
plt.show()
