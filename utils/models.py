"""
Pydantic models for the Smart Document Organizer API.

These models define the data structures used for request/response validation
and database operations, following the architecture specifications.
"""

import re
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

from pydantic import BaseModel, ConfigDict, Field, field_validator  # noqa: E402


class DocumentBase(BaseModel):
    """Base document model with common fields."""

    file_name: str = Field(..., min_length=1, max_length=255)
    file_type: str = Field(..., min_length=1, max_length=50)
    category: str = Field(..., min_length=1, max_length=100)
    file_path: Optional[str] = Field(None, max_length=500)
    primary_purpose: Optional[str] = Field(None, max_length=200)

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("File name cannot be empty")
        return v.strip()

    @field_validator("file_type")
    @classmethod
    def validate_file_type(cls, v: str) -> str:
        allowed_types = ["pd", "docx", "txt", "doc", "rt", "odt"]
        if v.lower() not in allowed_types:
            raise ValueError(f'File type must be one of: {", ".join(allowed_types)}')
        return v.lower()

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Category cannot be empty")
        return v.strip()


class DocumentCreate(DocumentBase):
    """Model for creating a new document."""

    content_text: Optional[str] = None
    content_type: str = Field(default="text/plain", max_length=100)


class DocumentUpdate(BaseModel):
    """Model for updating an existing document."""

    file_name: Optional[str] = Field(None, min_length=1, max_length=255)
    file_type: Optional[str] = Field(None, min_length=1, max_length=50)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    file_path: Optional[str] = Field(None, max_length=500)
    primary_purpose: Optional[str] = Field(None, max_length=200)
    content_text: Optional[str] = None
    content_type: Optional[str] = Field(None, max_length=100)


class DocumentResponse(DocumentBase):
    """Model for document API responses."""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    content_text: Optional[str] = None
    content_type: Optional[str] = None
    tags: List["TagResponse"] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class TagBase(BaseModel):
    """Base tag model."""

    tag_name: str = Field(..., min_length=1, max_length=100)
    tag_value: Optional[str] = Field(None, max_length=255)

    @field_validator("tag_name")
    @classmethod
    def validate_tag_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError(
                "Tag name can only contain alphanumeric characters, hyphens, and underscores"
            )
        return v.lower()


class TagCreate(TagBase):
    """Model for creating a new tag."""


class TagUpdate(BaseModel):
    """Model for updating an existing tag."""

    tag_name: Optional[str] = Field(None, min_length=1, max_length=100)
    tag_value: Optional[str] = Field(None, max_length=255)


class TagResponse(TagBase):
    """Model for tag API responses."""

    id: int
    document_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentTagCreate(BaseModel):
    """Model for associating tags with documents."""

    document_id: int = Field(..., gt=0)
    tags: List[TagCreate] = Field(..., min_length=1)


class SearchQuery(BaseModel):
    """Model for search requests."""

    query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    file_type: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = Field(None, max_length=10)
    limit: Optional[int] = Field(default=20, ge=1, le=100)
    offset: Optional[int] = Field(default=0, ge=0)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Search query cannot be empty")
        return v.strip()


class SearchResponse(BaseModel):
    """Model for search API responses."""

    documents: List[DocumentResponse]
    total_count: int
    query: str
    filters: Dict[str, Any]
    execution_time: float


class SearchSuggestionResponse(BaseModel):
    """Model for search suggestion responses."""

    suggestions: List[str]
    categories: List[str]
    tags: List[str]


class ErrorResponse(BaseModel):
    """Model for API error responses."""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class HealthResponse(BaseModel):
    """Model for health check responses."""

    status: str
    timestamp: datetime
    database_connected: bool
    version: str = "1.0.0"


class PaginatedResponse(BaseModel):
    """Generic paginated response model."""

    items: List[Any]
    total_count: int
    page: int
    page_size: int
    total_pages: int


# Update forward references
DocumentResponse.model_rebuild()
