from pydantic import BaseModel, Field

class Relationship(BaseModel):
    """A semantic relationship between two educational entities."""
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    inference_method: str


class RelationshipIndex(BaseModel):
    """A collection of inferred relationships for a book."""
    book_id: str
    relationships: list[Relationship] = Field(default_factory=list)
