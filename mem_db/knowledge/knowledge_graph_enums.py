from enum import Enum


class KnowledgeGraphType(Enum):
    """Types of knowledge graphs in the legal domain."""

    LEGAL_ENTITIES = "legal_entities"
    CASE_RELATIONSHIPS = "case_relationships"
    STATUTE_HIERARCHY = "statute_hierarchy"
    PRECEDENT_NETWORK = "precedent_network"
    LEGAL_CONCEPTS = "legal_concepts"


class RelationType(Enum):
    """Types of relationships in legal knowledge graphs."""

    REFERENCES = "references"
    CITES = "cites"
    OVERRULES = "overrules"
    DISTINGUISHES = "distinguishes"
    FOLLOWS = "follows"
    GOVERNED_BY = "governed_by"
    APPLIES_TO = "applies_to"
    DEFINES = "defines"
    MODIFIES = "modifies"
    SUPERSEDES = "supersedes"
    PRECEDES = "precedes"
    CONTEMPORANEOUS = "contemporaneous"
    SUBSEQUENT = "subsequent"
    PARENT_OF = "parent_o"
    CHILD_OF = "child_o"
    PART_OF = "part_o"
    CONTAINS = "contains"
    SIMILAR_TO = "similar_to"
    RELATED_TO = "related_to"
    CONFLICTS_WITH = "conflicts_with"
    SUPPORTS = "supports"


class LegalEntityType(Enum):
    """Extended legal entity types for specialized legal analysis."""

    CASE = "case"
    STATUTE = "statute"
    REGULATION = "regulation"
    COURT_DECISION = "court_decision"
    LEGAL_PRECEDENT = "legal_precedent"
    JUDGE = "judge"
    LAWYER = "lawyer"
    LAW_FIRM = "law_firm"
    COURT = "court"
    LEGAL_ENTITY = "legal_entity"
    PARTY = "party"


class LegalRelationshipType(Enum):
    """Extended legal relationship types for legal domain analysis."""

    CITES = "cites"
    CITED_BY = "cited_by"
    OVERRULES = "overrules"
    OVERRULED_BY = "overruled_by"
    DISTINGUISHES = "distinguishes"
    FOLLOWS = "follows"
    FILED_BY = "filed_by"
    REPRESENTS = "represents"
    DECIDED_BY = "decided_by"
