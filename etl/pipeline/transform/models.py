from pydantic import BaseModel, Field
from typing import Optional


class TransformedArtworkData(BaseModel):
    """
    Pydantic model for transformed artwork data.
    Data goes here after initial extraction and cleaning, and before loading
    into TransformedData Django model.
    """

    # Required fields
    object_number: str = Field(..., description="Required field - object identifier")
    museum_slug: str = Field(..., description="Required field - museum identifier")
    searchable_work_types: list[str] = Field(
        ..., description="Required field - standardized work types"
    )
    thumbnail_url: str = Field(..., description="Required field - thumbnail image URL")

    # Other fields
    title: Optional[str] = Field(
        default=None, description="Primary title of the artwork"
    )
    work_types: list[str] = Field(
        default_factory=list, description="Raw work type classifications"
    )
    artist: list[str] = Field(default_factory=list, description="Artist names")

    # Dating
    production_date_start: Optional[int] = Field(
        default=None, description="Start year of production"
    )
    production_date_end: Optional[int] = Field(
        default=None, description="End year of production"
    )
    period: Optional[str] = Field(
        default=None, max_length=100, description="Period designation"
    )

    # Image URL
    image_url: Optional[str] = Field(
        default=None, description="Full resolution image URL"
    )

    # Museum metadata
    museum_db_id: Optional[str] = Field(
        default=None, description="Museum's internal database ID"
    )

    # Processing status fields
    image_loaded: bool = Field(
        default=False, description="Whether image has been downloaded"
    )
    vector_loaded: bool = Field(
        default=False, description="Whether any vector embeddings exist"
    )

    # Vector storage tracking (for multiple embedding models)
    text_vector_clip: bool = Field(
        default=False, description="Whether CLIP text embedding exists"
    )
    image_vector_clip: bool = Field(
        default=False, description="Whether CLIP image embedding exists"
    )
    text_vector_jina: bool = Field(
        default=False, description="Whether Jina text embedding exists"
    )
    image_vector_jina: bool = Field(
        default=False, description="Whether Jina image embedding exists"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for Django model creation."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "TransformedArtworkData":
        """Create instance from dictionary."""
        return cls(**data)
