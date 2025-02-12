"""
2D projects typically preserve the local structure of the data, which means that similar
points in the original high-dimensional space will be close to each other in the 2D projection.
This property is useful for visualizing clusters or patterns in the data.
Global structure, on the other hand, may not be preserved as well in 2D projections.
"""

import umap
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
import requests
from io import BytesIO
from sklearn.preprocessing import normalize
from sklearn.decomposition import PCA
from artsearch.src.utils.get_qdrant_client import get_qdrant_client
from artsearch.src.config import config


# =============================================================================
# STEP 0: CONFIGURATION
# Choose the first projection method: 'UMAP' or 'PCA'
FIRST_PROJECTION_METHOD = 'PCA'
SOURCE_COLLECTION = config.qdrant_collection_name

# =============================================================================
# STEP 1: FETCH DATA FROM QDRANT AND NORMALIZE THE VECTORS
qdrant_client = get_qdrant_client()
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
# STEP 2: REDUCE DIMENSIONALITY FROM 512D TO 50D
# =============================================================================
if FIRST_PROJECTION_METHOD == 'UMAP':
    print("Reducing dimensionality from 512D to 50D using UMAP...")
    umap_model_50d = umap.UMAP(n_components=50, metric="euclidean", random_state=42)
    vectors_50d = umap_model_50d.fit_transform(vectors_512)
    print("50D reduction complete.")
elif FIRST_PROJECTION_METHOD == 'PCA':
    print("Reducing dimensionality from 512D to 50D using PCA...")
    pca_model = PCA(n_components=50, random_state=42)
    vectors_50d = pca_model.fit_transform(vectors_512)
    print("50D reduction complete.")
else:
    raise ValueError("Invalid value for FIRST_PROJECTION. Use 'UMAP' or 'PCA'.")
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
highlight_artists = ["C.W. Eckersberg", "Henri Matisse", "H.W. Bissen"]
highlight_colors = ["red", "lime", "blue"]  # Colors for highlighted artists
default_color = "lightgray"  # Color for non-highlighted points
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
# Set zorder explicitly so that scatter points are drawn above the image (if needed)
scatter = plt.scatter(
    vectors_2d[:, 0],  # type: ignore
    vectors_2d[:, 1],  # type: ignore
    c=point_colors,  # type: ignore
    s=point_sizes,  # type: ignore
    alpha=0.6,
    edgecolors="k" if highlight_artists else None,
    linewidth=0.5,
    zorder=2,  # scatter points drawn at level 2
)


# =============================================================================
# STEP 6: SET UP HOVER FUNCTIONALITY TO DISPLAY ANNOTATIONS & IMAGES
def fetch_image(url):
    """Fetch an image from a URL and return it as a PIL Image."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None


# Create an annotation box for metadata (initially invisible)
annot = plt.gca().annotate(
    "",
    xy=(0, 0),
    xytext=(15, 15),
    textcoords="offset points",
    bbox=dict(boxstyle="round", fc="w"),
    fontsize=12,
    arrowprops=dict(arrowstyle="->"),
)
annot.set_visible(False),
annot.set_zorder(3)  # draw metadata above scatter points and image
# Global placeholders for the image box and hovered point marker
image_box = None
hovered_point_marker = None


def update_annot(ind):
    """Update the annotation text and image box based on the hovered point."""
    global image_box, hovered_point_marker
    index = ind["ind"][0]
    pos = scatter.get_offsets()[index]  # type: ignore
    annot.xy = pos  # type: ignore
    annot.set_text(annotations[index])
    # Remove any existing image box (if present)
    if image_box is not None and image_box in plt.gca().artists:
        image_box.remove()
        image_box = None
    # If a thumbnail URL is available, fetch and display the image.
    # Use an offset (in display points) so that the image does not overlap the metadata box.
    if thumbnails[index]:
        img = fetch_image(thumbnails[index])
        if img:
            img.thumbnail((200, 200))  # Resize image as needed
            image = OffsetImage(img, zoom=1.2)  # type: ignore
            # Here we use xybox with "offset points" so that the image always appears, for example, 30 points to the right
            # and 30 points down from the hovered point. Adjust (30, -30) as needed.
            image_box = AnnotationBbox(
                image,
                pos,  # type: ignore
                xybox=(30, -30),
                xycoords='data',
                boxcoords="offset points",
                frameon=True,
                pad=0.3,
                bboxprops=dict(edgecolor="black"),
                zorder=1,  # draw image behind both scatter points and metadata text
            )
            plt.gca().add_artist(image_box)
    # Optionally, add a highlighted marker on top of the hovered point so it stays visible.
    # Remove previous marker if it exists.
    if hovered_point_marker is not None:
        hovered_point_marker.remove()
    hovered_point_marker = plt.gca().scatter(
        [pos[0]],  # type: ignore
        [pos[1]],  # type: ignore
        s=point_sizes[index] * 3,  # slightly larger for emphasis
        facecolors='none',
        edgecolors='black',
        linewidth=1.5,
        zorder=4,  # highest zorder so it appears on top
    )


def hover(event):
    """Event handler for mouse motion: update annotation when hovering over a point."""
    global hovered_point_marker
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
                # Remove the image box and hovered marker if they exist
                global image_box
                if image_box is not None and image_box in plt.gca().artists:
                    image_box.remove()
                    image_box = None
                if hovered_point_marker is not None:
                    hovered_point_marker.remove()
                    hovered_point_marker = None
                plt.gcf().canvas.draw_idle()


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
plt.savefig("artsearch/src/scripts/datascience_experiments/2d_proj_artists.png")
print("Done!")

input("Press Enter to continue...")  # Keeps the script open
