"""
Unit tests for bucket_service image resizing functionality.
"""
import pytest
from io import BytesIO
from PIL import Image
from etl.services.bucket_service import resize_image_with_aspect_ratio


@pytest.mark.unit
class TestImageResizing:
    """Unit tests for image resizing that don't require database or external services."""

    def test_resize_wide_image(self):
        """Test resizing a wide landscape image (3000×1000 → 800×266)."""
        # Create a test image
        img = Image.new("RGB", (3000, 1000), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        # Resize
        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=800)

        # Verify dimensions
        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.width == 800
        assert resized_img.height == 266  # 1000 * (800/3000) = 266.67 → 266
        assert resized_img.mode == "RGB"

    def test_resize_tall_image(self):
        """Test resizing a tall portrait image (1000×3000 → 266×800)."""
        img = Image.new("RGB", (1000, 3000), color="blue")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=800)

        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.width == 266  # 1000 * (800/3000) = 266.67 → 266
        assert resized_img.height == 800
        assert resized_img.mode == "RGB"

    def test_resize_square_image(self):
        """Test resizing a square image (2000×2000 → 800×800)."""
        img = Image.new("RGB", (2000, 2000), color="green")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=800)

        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.width == 800
        assert resized_img.height == 800
        assert resized_img.mode == "RGB"

    def test_resize_already_small_image(self):
        """Test that small images aren't upscaled (600×400 stays 600×400)."""
        img = Image.new("RGB", (600, 400), color="yellow")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=800)

        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.width == 600
        assert resized_img.height == 400
        assert resized_img.mode == "RGB"

    def test_resize_extreme_panorama(self):
        """Test resizing extreme aspect ratio (4000×500 → 800×100)."""
        img = Image.new("RGB", (4000, 500), color="purple")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=800)

        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.width == 800
        assert resized_img.height == 100  # 500 * (800/4000)
        assert resized_img.mode == "RGB"

    def test_convert_rgba_to_rgb(self):
        """Test that RGBA images are converted to RGB."""
        img = Image.new("RGBA", (2000, 1500), color=(255, 0, 0, 128))
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()

        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=800)

        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.mode == "RGB"  # Converted from RGBA
        assert resized_img.width == 800
        assert resized_img.height == 600

    def test_convert_grayscale_to_rgb(self):
        """Test that grayscale images are converted to RGB."""
        img = Image.new("L", (2000, 1500), color=128)
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=800)

        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.mode == "RGB"  # Converted from grayscale
        assert resized_img.width == 800
        assert resized_img.height == 600

    def test_custom_max_dimension(self):
        """Test using a custom max dimension parameter."""
        img = Image.new("RGB", (2000, 1000), color="orange")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=400)

        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.width == 400
        assert resized_img.height == 200

    def test_custom_jpeg_quality(self):
        """Test that JPEG quality parameter is applied (file size check)."""
        img = Image.new("RGB", (2000, 1500), color="cyan")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        # High quality should produce larger files
        high_quality = resize_image_with_aspect_ratio(
            img_bytes, max_dimension=800, jpeg_quality=95
        )
        low_quality = resize_image_with_aspect_ratio(
            img_bytes, max_dimension=800, jpeg_quality=50
        )

        assert len(high_quality) > len(low_quality)

    def test_output_is_jpeg(self):
        """Test that output is always JPEG format."""
        img = Image.new("RGB", (2000, 1500), color="magenta")
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")  # Input as PNG
        img_bytes = img_bytes.getvalue()

        resized_bytes = resize_image_with_aspect_ratio(img_bytes, max_dimension=800)

        # Verify output is JPEG
        resized_img = Image.open(BytesIO(resized_bytes))
        assert resized_img.format == "JPEG"
