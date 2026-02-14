"""
Document-related database models
"""

from sqlalchemy import (
    JSON,
    Column,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import relationship  # noqa: E402

from .base import Base, BaseModel  # noqa: E402


class Document(Base, BaseModel):
    """Document model"""

    __tablename__ = "documents"

    title = Column(String(500), nullable=False, doc="Document title")

    file_path = Column(String(1000), doc="Original file path")

    file_name = Column(String(255), doc="Original file name")

    file_type = Column(String(50), doc="File type (pdf, docx, txt, etc.)")

    file_size = Column(Integer, doc="File size in bytes")

    contenttext = Column(Text, doc="Extracted text content")

    content_hash = Column(String(64), doc="SHA256 hash of content")

    document_type = Column(
        String(100), doc="Legal document type (contract, case law, statute, etc.)"
    )

    jurisdiction = Column(String(100), doc="Legal jurisdiction")

    language = Column(String(10), default="en", doc="Document language")

    processing_status = Column(
        String(50),
        default="pending",
        doc="Processing status (pending, processed, failed)",
    )

    processing_metadata = Column(JSON, default=dict, doc="Processing metadata")

    # Relationships
    analyses = relationship(
        "DocumentAnalysis", back_populates="document", cascade="all, delete-orphan"
    )
    extractions = relationship(
        "EntityExtraction", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentAnalysis(Base, BaseModel):
    """Document analysis results model"""

    __tablename__ = "document_analyses"

    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Document ID",
    )

    analysis_type = Column(
        String(100),
        nullable=False,
        doc="Type of analysis (irac, toulmin, summary, etc.)",
    )

    analyzer_name = Column(String(255), doc="Name of analyzer that performed analysis")

    analyzer_version = Column(String(50), doc="Version of analyzer")

    analysis_results = Column(JSON, nullable=False, doc="Analysis results")

    confidence_score = Column(Float, doc="Confidence score (0.0 - 1.0)")

    processing_time_ms = Column(Integer, doc="Processing time in milliseconds")

    # Relationships
    document = relationship("Document", back_populates="analyses")


class EntityExtraction(Base, BaseModel):
    """Entity extraction results model"""

    __tablename__ = "entity_extractions"

    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Document ID",
    )

    entity_type = Column(
        String(100),
        nullable=False,
        doc="Type of entity (PERSON, ORG, LEGAL_CONCEPT, etc.)",
    )

    entitytext = Column(Text, nullable=False, doc="Extracted entity text")

    entity_normalized = Column(String(500), doc="Normalized entity value")

    start_position = Column(Integer, doc="Start position in document")

    end_position = Column(Integer, doc="End position in document")

    confidence_score = Column(Float, doc="Extraction confidence (0.0 - 1.0)")

    extractor_name = Column(String(255), doc="Name of extractor")

    context = Column(Text, doc="Surrounding context")

    metadata_json = Column(JSON, default=dict, doc="Additional extraction metadata")

    # Relationships
    document = relationship("Document", back_populates="extractions")


class DocumentEmbedding(Base, BaseModel):
    """Document embeddings for semantic search"""

    __tablename__ = "document_embeddings"

    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Document ID",
    )

    embedding_model = Column(
        String(255), nullable=False, doc="Model used for embedding"
    )

    embedding_version = Column(String(50), doc="Version of embedding model")

    embedding_data = Column(LargeBinary, doc="Binary embedding data")

    embedding_dimension = Column(Integer, doc="Dimension of embedding vector")

    text_chunk = Column(Text, doc="Text chunk that was embedded")

    chunk_index = Column(Integer, default=0, doc="Index of chunk in document")
