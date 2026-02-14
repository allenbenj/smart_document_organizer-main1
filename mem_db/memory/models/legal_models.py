"""
Legal domain-specific database models
"""

from sqlalchemy import (
    JSON,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship  # noqa: E402

from .base import Base, BaseModel  # noqa: E402


class LegalCase(Base, BaseModel):
    """Legal case model"""

    __tablename__ = "legal_cases"

    case_name = Column(String(500), nullable=False, doc="Full case name")

    citation = Column(String(255), doc="Legal citation")

    court = Column(String(255), doc="Court name")

    jurisdiction = Column(String(100), doc="Legal jurisdiction")

    decision_date = Column(Date, doc="Date of decision")

    case_number = Column(String(100), doc="Court case number")

    case_type = Column(String(100), doc="Type of case (civil, criminal, etc.)")

    legal_area = Column(String(100), doc="Area of law")

    summary = Column(Text, doc="Case summary")

    holding = Column(Text, doc="Court's holding")

    precedential_value = Column(
        String(50), doc="Precedential value (binding, persuasive, etc.)"
    )

    # Relationships
    entities = relationship("LegalEntity", back_populates="case")
    citations = relationship(
        "Citation", foreign_keys="Citation.citing_case_id", back_populates="citing_case"
    )


class LegalEntity(Base, BaseModel):
    """Legal entity model (people, organizations, concepts)"""

    __tablename__ = "legal_entities"

    entity_name = Column(String(500), nullable=False, doc="Entity name")

    entity_type = Column(
        String(100),
        nullable=False,
        doc="Entity type (PERSON, ORG, LEGAL_CONCEPT, etc.)",
    )

    entity_subtype = Column(String(100), doc="Entity subtype")

    description = Column(Text, doc="Entity description")

    aliases = Column(JSON, default=list, doc="Alternative names/aliases")

    attributes = Column(JSON, default=dict, doc="Entity attributes")

    confidence_score = Column(
        Float, default=1.0, doc="Confidence in entity identification"
    )

    case_id = Column(
        String(36),
        ForeignKey("legal_cases.id", ondelete="CASCADE"),
        doc="Associated case ID",
    )

    # Relationships
    case = relationship("LegalCase", back_populates="entities")
    relationships_as_source = relationship(
        "LegalRelationship", foreign_keys="LegalRelationship.source_entity_id"
    )
    relationships_as_target = relationship(
        "LegalRelationship", foreign_keys="LegalRelationship.target_entity_id"
    )


class LegalRelationship(Base, BaseModel):
    """Relationships between legal entities"""

    __tablename__ = "legal_relationships"

    source_entity_id = Column(
        String(36),
        ForeignKey("legal_entities.id", ondelete="CASCADE"),
        nullable=False,
        doc="Source entity ID",
    )

    target_entity_id = Column(
        String(36),
        ForeignKey("legal_entities.id", ondelete="CASCADE"),
        nullable=False,
        doc="Target entity ID",
    )

    relationship_type = Column(String(100), nullable=False, doc="Type of relationship")

    relationship_description = Column(Text, doc="Description of relationship")

    confidence_score = Column(Float, default=1.0, doc="Confidence in relationship")

    evidence = Column(JSON, default=list, doc="Evidence supporting relationship")

    # Relationships
    source_entity = relationship("LegalEntity", foreign_keys=[source_entity_id])
    target_entity = relationship("LegalEntity", foreign_keys=[target_entity_id])


class Citation(Base, BaseModel):
    """Legal citations between cases"""

    __tablename__ = "citations"

    citing_case_id = Column(
        String(36),
        ForeignKey("legal_cases.id", ondelete="CASCADE"),
        nullable=False,
        doc="Case making the citation",
    )

    cited_case_id = Column(
        String(36),
        ForeignKey("legal_cases.id", ondelete="CASCADE"),
        nullable=False,
        doc="Case being cited",
    )

    citation_type = Column(
        String(50), doc="Type of citation (positive, negative, neutral)"
    )

    citationcontext = Column(Text, doc="Context of citation")

    page_number = Column(Integer, doc="Page number of citation")

    treatment = Column(String(100), doc="How the cited case is treated")

    # Relationships
    citing_case = relationship("LegalCase", foreign_keys=[citing_case_id])
    cited_case = relationship("LegalCase", foreign_keys=[cited_case_id])


class LegalConcept(Base, BaseModel):
    """Legal concepts and principles"""

    __tablename__ = "legal_concepts"

    concept_name = Column(
        String(255), nullable=False, unique=True, doc="Legal concept name"
    )

    concept_type = Column(
        String(100), doc="Type of concept (doctrine, principle, test, etc.)"
    )

    definition = Column(Text, doc="Definition of concept")

    legal_area = Column(String(100), doc="Area of law")

    jurisdiction = Column(String(100), doc="Applicable jurisdiction")

    synonyms = Column(JSON, default=list, doc="Synonymous terms")

    related_concepts = Column(JSON, default=list, doc="Related legal concepts")

    source_authority = Column(
        String(500), doc="Source of authority (statute, case, etc.)"
    )
