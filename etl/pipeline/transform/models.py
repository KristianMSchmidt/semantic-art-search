from pydantic import BaseModel, Field
from typing import Optional


class TransformedArtworkData(BaseModel):
    """
    Pydantic model for transformed artwork data.
    
    This represents the cleaned and standardized data ready for embedding
    generation and vector database upload. Fields match Django TransformedData model.
    """
    
    # Core identification
    object_number: str = Field(..., description="Required field - object identifier")
    title: Optional[str] = Field(default=None, description="Primary title of the artwork")
    
    # Classification
    work_types: list[str] = Field(default_factory=list, description="Raw work type classifications")
    searchable_work_types: list[str] = Field(..., description="Required field - standardized work types")
    
    # Creator information
    artist: list[str] = Field(default_factory=list, description="Artist names")
    
    # Dating
    production_date_start: Optional[int] = Field(default=None, description="Start year of production")
    production_date_end: Optional[int] = Field(default=None, description="End year of production") 
    period: Optional[str] = Field(default=None, max_length=100, description="Period designation")
    
    # Images and URLs
    thumbnail_url: str = Field(..., description="Required field - thumbnail image URL")
    image_url: Optional[str] = Field(default=None, description="Full resolution image URL")
    
    # Museum metadata
    museum_slug: str = Field(..., description="Required field - museum identifier")
    museum_db_id: Optional[str] = Field(default=None, description="Museum's internal database ID")
    museum_frontend_url: str = Field(default="", description="Public link to artwork on museum homepage")
    
    # External links
    object_url: Optional[str] = Field(default=None, description="API link to full metadata")
    
    # Processing status flags
    image_loaded: bool = Field(default=False, description="Whether image has been downloaded")
    text_vector_clip: bool = Field(default=False, description="Whether CLIP text embedding exists")
    image_vector_clip: bool = Field(default=False, description="Whether CLIP image embedding exists")
    text_vector_jina: bool = Field(default=False, description="Whether Jina text embedding exists")
    image_vector_jina: bool = Field(default=False, description="Whether Jina image embedding exists")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Django model creation."""
        return self.model_dump()
        
    @classmethod
    def from_dict(cls, data: dict) -> "TransformedArtworkData":
        """Create instance from dictionary."""
        return cls(**data)