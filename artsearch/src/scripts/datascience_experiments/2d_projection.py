import umap
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
import requests
from io import BytesIO
from tqdm import tqdm
from sklearn.preprocessing import normalize
from qdrant_client.http.models import PointStruct
from artsearch.src.services.qdrant_service import get_qdrant_service

# =============================================================================
# STEP 1: FETCH DATA FROM THE ORIGINAL COLLECTION (512D embeddings)
# =============================================================================

# Initialize Qdrant service
qdrant_service = get_qdrant_service()
qdrant_client = qdrant_service.qdrant_client

# Define source collection name
SOURCE_COLLECTION = "smk_artworks"

print("Fetching data from Qdrant...")
# The scroll method returns a tuple: (list_of_points, next_page_offset)
points_data, _ = qdrant_client.scroll(
    SOURCE_COLLECTION, scroll_filter=None, with_vectors=True, limit=10_000
)

vectors_512 = []
metadata_list = []
ids = []

for point in points_data:
    vectors_512.append(point.vector)
    metadata_list.append(point.payload)  # Preserve metadata for later
    ids.append(point.id)

vectors_512 = np.array(vectors_512)
vectors_512 = normalize(vectors_512, norm="l2")  # Normalize embeddings

print(f"Loaded {len(vectors_512)} vectors with shape: {vectors_512.shape}")
print("L2 norm of first vector:", np.linalg.norm(vectors_512[0]))

# =============================================================================
# STEP 2: REDUCE DIMENSIONALITY FROM 512D TO 50D USING UMAP
# =============================================================================

print("Reducing dimensionality from 512D to 50D...")
umap_model_50d = umap.UMAP(n_components=50, metric="euclidean", random_state=42)
vectors_50d = umap_model_50d.fit_transform(vectors_512)
print("50D reduction complete.")

# (Note: We are not uploading the 50D embeddings to Qdrant here,
#  which avoids the extra upload/download step.)

# =============================================================================
# STEP 3: FURTHER REDUCE FROM 50D TO 2D FOR VISUALIZATION
# =============================================================================

print("Reducing dimensionality from 50D to 2D for visualization...")
umap_model_2d = umap.UMAP(n_components=2, metric="euclidean", random_state=42)
vectors_2d = umap_model_2d.fit_transform(vectors_50d)
print("2D reduction complete.")

# =============================================================================
# STEP 4: PREPARE ANNOTATIONS & THUMBNAILS FOR VISUALIZATION
# =============================================================================

annotations = []
thumbnails = []
artists_list = []  # To store artist names for color coding

for payload in metadata_list:
    # Ensure the payload is a dictionary
    payload_dict = dict(payload)
    # Safely extract artist information (assuming it's stored as a list)
    artist = (
        payload_dict.get("artist", ["Unknown"])[0]
        if "artist" in payload_dict
        else "Unknown"
    )
    titles = payload_dict.get("titles", [])
    title = titles[0].get("title", "Unknown") if titles else "Unknown"
    thumbnail_url = payload_dict.get("thumbnail_url", None)

    annotations.append(f"Artist: {artist}\nTitle: {title}")
    thumbnails.append(thumbnail_url)
    artists_list.append(artist)

# =============================================================================
# STEP 5: CREATE THE SCATTER PLOT WITH HOVER FUNCTIONALITY
# =============================================================================

print("Creating scatter plot visualization...")
plt.figure(figsize=(21, 15))

# Define artists to highlight and their colors
highlight_artists = ["Vilhelm Lundstrøm", "C.W. Eckersberg", "Henri Matisse"]
highlight_colors = ["red", "orange", "lime"]  # Colors for highlighted artists
default_color = "lightgray"  # Color for non-highlighted points

# Create a color mapping based on highlighted artists
color_map = {
    artist: color for artist, color in zip(highlight_artists, highlight_colors)
}
point_colors = [color_map.get(artist, default_color) for artist in artists_list]

# Define point sizes: larger for highlighted artists, smaller for others
highlight_size = 80
default_size = 2
point_sizes = [
    highlight_size if artist in highlight_artists else default_size
    for artist in artists_list
]

# Plot the points using the 2D UMAP coordinates
scatter = plt.scatter(
    vectors_2d[:, 0],
    vectors_2d[:, 1],
    c=point_colors,
    s=point_sizes,
    alpha=0.6,
    edgecolors="k" if highlight_artists else None,
    linewidth=0.5,
)

# =============================================================================
# STEP 6: SET UP HOVER FUNCTIONALITY TO DISPLAY ANNOTATIONS & IMAGES
# =============================================================================


def fetch_image(url):
    """Fetch an image from a URL and return it as a PIL Image."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None


# Create an annotation box (initially invisible)
annot = plt.gca().annotate(
    "",
    xy=(0, 0),
    xytext=(15, 15),
    textcoords="offset points",
    bbox=dict(boxstyle="round", fc="w"),
    fontsize=12,
    arrowprops=dict(arrowstyle="->"),
)
annot.set_visible(False)

image_box = None  # Placeholder for the image box


def update_annot(ind):
    """Update the annotation text and image box based on the hovered point."""
    index = ind["ind"][0]
    pos = scatter.get_offsets()[index]
    annot.xy = pos
    annot.set_text(annotations[index])

    global image_box
    # Remove any existing image box
    if image_box is not None and image_box in plt.gca().artists:
        image_box.remove()
        image_box = None

    # If a thumbnail URL is available, fetch and display the image
    if thumbnails[index]:
        img = fetch_image(thumbnails[index])
        if img:
            img.thumbnail((200, 200))  # Resize image as needed
            image = OffsetImage(img, zoom=1.2)
            image_box = AnnotationBbox(
                image,
                (pos[0], pos[1] - 1),  # Adjust position as needed
                frameon=True,
                pad=0.3,
                bboxprops=dict(edgecolor="black"),
            )
            plt.gca().add_artist(image_box)


def hover(event):
    """Event handler for mouse motion: update annotation when hovering over a point."""
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


# Connect the hover event to the handler
plt.gcf().canvas.mpl_connect("motion_notify_event", hover)

# =============================================================================
# STEP 7: ADD A LEGEND AND FINAL PLOT SETTINGS
# =============================================================================

# Manually add legend entries for the highlighted artists
for artist, color in color_map.items():
    plt.scatter([], [], c=color, s=highlight_size, label=artist)

plt.legend(loc="upper right", title="Highlighted Artists", fontsize="large")
plt.title("2D UMAP Projection with Hover Annotations and Images", fontsize=16)
plt.xlabel("UMAP Dimension 1", fontsize=12)
plt.ylabel("UMAP Dimension 2", fontsize=12)

plt.show()
print("Done!")
