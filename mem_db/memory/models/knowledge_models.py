"""
Knowledge graph database models
"""

from sqlalchemy import JSON, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship  # noqa: E402

from .base import Base, BaseModel  # noqa: E402


class KnowledgeNode(Base, BaseModel):
    """Knowledge graph nodes"""

    __tablename__ = "knowledge_nodes"

    node_type = Column(
        String(100), nullable=False, doc="Type of node (entity, concept, case, etc.)"
    )

    label = Column(String(500), nullable=False, doc="Node label/name")

    description = Column(Text, doc="Node description")

    properties = Column(JSON, default=dict, doc="Node properties")

    confidence_score = Column(Float, default=1.0, doc="Confidence in node data")

    source_document_id = Column(String(36), doc="Source document ID if applicable")

    # Relationships
    outgoing_edges = relationship(
        "KnowledgeEdge",
        foreign_keys="KnowledgeEdge.source_node_id",
        back_populates="source_node",
    )
    incoming_edges = relationship(
        "KnowledgeEdge",
        foreign_keys="KnowledgeEdge.target_node_id",
        back_populates="target_node",
    )


class KnowledgeEdge(Base, BaseModel):
    """Knowledge graph edges/relationships"""

    __tablename__ = "knowledge_edges"

    source_node_id = Column(
        String(36),
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        doc="Source node ID",
    )

    target_node_id = Column(
        String(36),
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        doc="Target node ID",
    )

    relationship_type = Column(String(100), nullable=False, doc="Type of relationship")

    relationship_label = Column(String(255), doc="Human-readable relationship label")

    weight = Column(Float, default=1.0, doc="Relationship weight/strength")

    confidence_score = Column(Float, default=1.0, doc="Confidence in relationship")

    properties = Column(JSON, default=dict, doc="Edge properties")

    evidence = Column(JSON, default=list, doc="Evidence supporting relationship")

    # Relationships
    source_node = relationship(
        "KnowledgeNode", foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target_node = relationship(
        "KnowledgeNode", foreign_keys=[target_node_id], back_populates="incoming_edges"
    )


class OntologyEntity(Base, BaseModel):
    """Legal ontology entities"""

    __tablename__ = "ontology_entities"

    entity_uri = Column(
        String(500), unique=True, nullable=False, doc="Unique URI for entity"
    )

    entity_type = Column(String(100), nullable=False, doc="Ontology entity type")

    preferred_label = Column(String(255), nullable=False, doc="Preferred label")

    alternative_labels = Column(JSON, default=list, doc="Alternative labels")

    definition = Column(Text, doc="Entity definition")

    hierarchy_level = Column(Integer, default=0, doc="Level in hierarchy")

    parent_entity_id = Column(
        String(36), ForeignKey("ontology_entities.id"), doc="Parent entity ID"
    )

    properties = Column(JSON, default=dict, doc="Entity properties")

    usage_count = Column(Integer, default=0, doc="Number of times used")

    # Relationships
    parent = relationship(
        "OntologyEntity", remote_side="OntologyEntity.id", backref="children"
    )


class ConceptMapping(Base, BaseModel):
    """Mappings between different concept representations"""

    __tablename__ = "concept_mappings"

    source_concept_id = Column(String(36), doc="Source concept ID")

    target_concept_id = Column(String(36), doc="Target concept ID")

    mapping_type = Column(
        String(100),
        nullable=False,
        doc="Type of mapping (equivalent, broader, narrower, related)",
    )

    confidence_score = Column(Float, default=1.0, doc="Mapping confidence")

    mapping_source = Column(
        String(255), doc="Source of mapping (manual, automated, etc.)"
    )

    evidence = Column(JSON, default=dict, doc="Evidence for mapping")
