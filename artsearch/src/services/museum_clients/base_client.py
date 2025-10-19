from abc import ABC, abstractmethod


class MuseumAPIClient(ABC):
    """Abstract base class for museum API clients."""

    @abstractmethod
    def get_object_url(self, object_number: str) -> str:
        """Construct the API URL for a given object number or museum database ID."""
        pass

    @abstractmethod
    def get_page_url(self, object_number: str) -> str:
        """Construct the museum's public page URL for a given object number or museum database ID."""
        pass
