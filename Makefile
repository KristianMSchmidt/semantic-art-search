find-similar-images:
	python -m scripts.find_similar_images

run-text-search:
	python -m scripts.text_search

run-upload-to-qdrant:
	python -m scripts.upload_to_qdrant

help:
	@echo "Available commands:"
	@echo "  make run-similar-images    - Run the similar_images script as a module"
	@echo "  make run-text-search       - Run the text_search script as a module"
	@echo "  make run-upload-to-qdrant  - Run the upload_to_qdrant script as a module"
	@echo "  make help                  - Display this help message"
