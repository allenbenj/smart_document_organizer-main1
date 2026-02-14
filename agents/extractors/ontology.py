# legal_ai_system/utils/ontology.py
"""
Legal ontology definitions with comprehensive prompt hints for LLM-assisted extraction.

This module provides the legal domain ontology with enhanced metadata to guide
AI systems in extracting structured information from legal documents.
"""

from __future__ import (  # Important for forward references if types are complex
    annotations,
)

from collections import namedtuple  # noqa: E402
from enum import Enum  # noqa: E402
from typing import Any, Dict, Iterable, List, Optional  # Added Optional  # noqa: E402

# If LegalDocument is a Pydantic model or dataclass defined elsewhere,
# it would be imported, e.g., from legal_ai_system.core.models import LegalDocument
# For now, assuming it's either not strictly needed for this file's core logic
# or will be resolved with a central types definition.


EntityMeta = namedtuple("EntityMeta", ["label", "attributes", "prompt_hint"])
RelMeta = namedtuple("RelMeta", ["label", "properties", "prompt_hint"])


# Helper functions remain as they are, they are internal to this module's setup
def _EntityMetaHelper(
    data: tuple,
) -> EntityMeta:  # Renamed for clarity and added type hint
    """Helper function to handle the enum definition from source ontology."""
    return EntityMeta(data[0], data[1], data[2])


def _RelMetaHelper(data: tuple) -> RelMeta:  # Renamed for clarity and added type hint
    """Helper function to handle relationship enum definition."""
    return RelMeta(data[0], data[1], data[2])


class LegalEntityType(Enum):
    """
    Comprehensive legal entity types with AI-friendly prompt hints.
    Each entity includes attributes to extract and context hints for LLM guidance.
    """

    # Core People and Parties
    PERSON = _EntityMetaHelper(
        (
            "Person",
            ["name", "role"],
            "Any individual involved in the case - extract full names and their role/title.",
        )
    )
    WITNESS = _EntityMetaHelper(
        (
            "Witness",
            ["name", "contact_information"],
            "Individual who provides testimony - look for phrases like 'testified', 'stated', 'declared'.",
        )
    )
    PARTY = _EntityMetaHelper(
        (
            "Party",
            ["name", "role"],
            "Collective entity like company, agency, or organization involved in the case.",
        )
    )
    JUDGE = _EntityMetaHelper(
        (
            "Judge",
            ["name", "court", "jurisdiction"],
            "Presiding judge - look for 'Judge', 'Justice', 'Hon.', 'Honorable' titles.",
        )
    )
    PROSECUTOR = _EntityMetaHelper(
        (
            "Prosecutor",
            ["name", "office", "jurisdiction"],
            "Prosecuting attorney - look for 'DA', 'District Attorney', 'State Attorney'.",
        )
    )
    DEFENSECOUNSEL = _EntityMetaHelper(
        (
            "DefenseCounsel",
            ["name", "firm"],
            "Defense attorney - look for 'Attorney for', 'Counsel', 'Esq.', law firm names.",
        )
    )
    EXPERTWITNESS = _EntityMetaHelper(
        (
            "ExpertWitness",
            ["name", "field_of_expertise"],  # Renamed attribute
            "Specialist witness - look for professional titles, PhD, MD, certifications.",
        )
    )
    VICTIM = _EntityMetaHelper(
        (
            "Victim",
            ["name", "case_id_reference"],  # Renamed attribute
            "Victim in the case - often referenced as 'victim', 'complainant', 'injured party'.",
        )
    )

    # Legal Documents and Filings
    LEGALDOCUMENT = _EntityMetaHelper(
        (
            "LegalDocument",
            ["title", "filed_date", "document_type"],  # Added document_type
            "Formal pleadings, orders, briefs - look for document types like Motion, Order, Brief.",
        )
    )
    MOTION = _EntityMetaHelper(
        (
            "Motion",
            ["motion_title", "filed_on", "status", "outcome"],  # Renamed attributes
            "Filed motion - look for 'Motion to', 'Motion for', filing dates and outcomes.",
        )
    )
    ORDER = _EntityMetaHelper(
        (
            "Order",
            ["order_title", "ruled_on", "status", "outcome"],  # Renamed attributes
            "Court order - look for 'Orders', 'Decrees', judicial rulings and their dates.",
        )
    )
    STATEMENT = _EntityMetaHelper(
        (
            "Statement",
            [
                "speaker_name",
                "statement_date",
                "medium",
                "verbatim_text",
            ],  # Renamed attributes
            "Discrete testimony - extract who said what, when, and in what context.",
        )
    )

    # Case and Procedural Elements
    CASE = _EntityMetaHelper(
        (
            "Case",
            [
                "case_title",
                "case_number",
                "status",
                "jurisdiction",
                "court_name",
            ],  # Added case_number, court_name
            "Legal case container - look for case numbers, 'v.' or 'vs.', docket numbers.",
        )
    )
    HEARING = _EntityMetaHelper(
        (
            "Hearing",
            [
                "hearing_date",
                "hearing_type",
                "location",
                "presiding_judge_name",
            ],  # Added hearing_type, presiding_judge_name
            "Court session - look for hearing dates, courtroom numbers, session types.",
        )
    )
    LEGALISSUE = _EntityMetaHelper(
        (
            "LegalIssue",
            [
                "issue_description",
                "status",
                "relevant_law",
            ],  # Renamed, added relevant_law
            "Specific legal issue - constitutional questions, statutory interpretations, disputes.",
        )
    )
    EVENT = _EntityMetaHelper(
        (
            "Event",
            ["event_name", "event_date", "location"],  # Renamed, added location
            "Generic legal event - incidents, meetings, deadlines, significant occurrences.",
        )
    )
    CASEEVENT = _EntityMetaHelper(
        (
            "CaseEvent",
            [
                "event_name",
                "event_date",
                "event_type",
                "related_case_id",
            ],  # Added related_case_id
            "Timeline event - arraignments, depositions, settlements, key case milestones.",
        )
    )

    # Evidence and Investigation
    EVIDENCEITEM = _EntityMetaHelper(
        (
            "EvidenceItem",
            [
                "item_description",
                "evidence_type",
                "collected_date",
                "source_description",
                "item_hash",
                "location_found",
                "chain_of_custody_details",
            ],  # Renamed/clarified attributes
            "Physical or digital evidence - documents, photos, recordings, physical objects with chain of custody.",
        )
    )

    # Charges and Legal Violations
    INDICTMENTCOUNT = _EntityMetaHelper(
        (
            "IndictmentCount",
            [
                "count_identifier",
                "charge_description",
                "statute_citation",
            ],  # Renamed attributes
            "Specific charge - look for 'Count I', 'Count 1', numbered charges with statutory citations.",
        )
    )
    OFFENSE = _EntityMetaHelper(
        (
            "Offense",
            [
                "offense_description",
                "statute_citation",
                "severity_level",
            ],  # Renamed, added severity_level
            "Criminal offense - crimes, violations, infractions with legal code references.",
        )
    )
    LEGAL_VIOLATION = _EntityMetaHelper(
        (
            "LegalViolation",
            [
                "violation_type",
                "description",
                "date_of_violation",
                "violating_party_name",
            ],  # Added for clarity
            "A specific breach of law or regulation, e.g., Brady violation, 4th Amendment violation.",
        )
    )

    # Institutional Entities
    COURT = _EntityMetaHelper(
        (
            "Court",
            ["court_name", "court_level", "jurisdiction_name"],  # Renamed attributes
            "Court entity - District, Superior, Circuit, Federal courts with jurisdictional info.",
        )
    )
    LAWENFORCEMENTAGENCY = _EntityMetaHelper(
        (
            "LawEnforcementAgency",
            [
                "agency_name",
                "jurisdiction_name",
                "agency_type",
            ],  # Renamed, added agency_type
            "Police or similar agency - FBI, local police, sheriff departments, regulatory agencies.",
        )
    )

    # Agreements and Resolutions
    PLEADEAL = _EntityMetaHelper(
        (
            "PleaDeal",
            [
                "agreement_date",
                "terms_summary",
                "charges_involved",
            ],  # Added charges_involved
            "Plea agreement - look for 'plea bargain', 'plea agreement', negotiated settlements.",
        )
    )
    SANCTION = _EntityMetaHelper(
        (
            "Sanction",
            [
                "sanctioned_party_name",
                "reason_for_sanction",
                "sanction_type",
                "severity_level",
                "imposing_authority_name",
            ],  # Clarified attributes
            "Penalty imposed - fines, suspensions, disciplinary actions with reasoning.",
        )
    )

    # Task Management
    TASK = _EntityMetaHelper(
        (
            "Task",
            [
                "task_description",
                "due_date",
                "assigned_to_name",
                "status",
                "priority_level",
            ],  # Added priority_level
            "Action item or deadline - things to be done, filing deadlines, court-ordered actions.",
        )
    )

    # More Granular Types from memory_management.md
    STATUTE = _EntityMetaHelper(
        (
            "Statute",
            ["statute_name", "citation", "jurisdiction_name", "effective_date"],
            "A specific law or act passed by a legislative body.",
        )
    )
    REGULATION = _EntityMetaHelper(
        (
            "Regulation",
            ["regulation_title", "citation", "issuing_agency_name", "effective_date"],
            "A rule or order issued by an executive authority or regulatory agency.",
        )
    )
    JURISDICTION = _EntityMetaHelper(
        (
            "Jurisdiction",
            ["jurisdiction_name", "level", "governing_body_name"],
            "The official power to make legal decisions and judgments, or a geographical area of authority.",
        )
    )
    MONETARY_AMOUNT = _EntityMetaHelper(
        (
            "MonetaryAmount",
            ["amount", "currency", "context_description"],
            "A sum of money, e.g., fine, settlement, damages.",
        )
    )
    DATE_ENTITY = _EntityMetaHelper(
        (
            "DateEntity",
            [
                "date_value",
                "date_type",
                "context_description",
            ],  # Renamed from DATE to avoid conflict
            "A specific date mentioned, e.g., filing date, event date, birth date.",
        )
    )
    LOCATION_ENTITY = _EntityMetaHelper(
        (
            "LocationEntity",
            [
                "location_name",
                "location_type",
                "address_details",
            ],  # Renamed from LOCATION
            "A geographical place relevant to the case, e.g., crime scene, court location.",
        )
    )
    CONCEPT = _EntityMetaHelper(
        (
            "Concept",
            ["concept_name", "description", "domain"],
            "An abstract legal idea or principle, e.g., 'due process', 'negligence'.",
        )
    )

    def __str__(self) -> str:
        return self.value.label

    @property
    def attributes(self) -> List[str]:
        return self.value.attributes

    @property
    def prompt_hint(self) -> str:
        return self.value.prompt_hint

    @classmethod
    def validate_attrs(
        cls, ent_type_enum_val: "LegalEntityType", attrs: Dict[str, Any]
    ) -> bool:  # Corrected type hint
        """Validate that an entity has all required attributes."""
        # This method might be too strict if attributes are optional.
        # Consider if all attributes in EntityMeta are truly "required".
        # For now, it checks if all listed attributes are present as keys.
        missing = [a for a in ent_type_enum_val.attributes if a not in attrs]
        if missing:
            # Consider logging a warning instead of raising an error for flexibility during extraction
            # logger.warning(f"Entity type {ent_type_enum_val.value.label} is missing attributes: {missing}")
            return False
        return True


class LegalRelationshipType(Enum):
    """
    Legal relationship types with AI-friendly prompt hints for extraction guidance.
    Each relationship connects entities and includes properties to extract.
    """

    # Document and Filing Relationships
    FILED_BY = _RelMetaHelper(
        (
            "Filed_By",
            ["filed_date", "document_type_filed"],  # Added document_type_filed
            "Document filed by entity - look for 'filed by', 'submitted by', filing timestamps.",
        )
    )
    RULED_BY = _RelMetaHelper(
        (
            "Ruled_By",
            ["ruled_date", "ruling_summary"],  # Added ruling_summary
            "Order ruled by judge/court - look for 'ruled', 'decided', 'ordered by' with dates.",
        )
    )
    PRESIDED_BY = _RelMetaHelper(
        (
            "Presided_By",
            ["session_date", "case_number_involved"],  # Added case_number_involved
            "Judge presiding over hearing/case - 'presided over', 'heard before Judge'.",
        )
    )
    ADDRESSES = _RelMetaHelper(
        (
            "Addresses",
            [
                "relevance_score",
                "addressed_issue_description",
            ],  # Added relevance_score, addressed_issue_description
            "Motion/document addresses issue - what legal issues are being tackled.",
        )
    )

    # Evidence and Argumentation
    SUPPORTS = _RelMetaHelper(
        (
            "Supports",
            [
                "confidence_score",
                "reasoning_summary",
                "evidence_item_id",
            ],  # Added evidence_item_id
            "Evidence supports claim/argument - look for 'supports', 'corroborates', 'proves', 'demonstrates'.",
        )
    )
    REFUTES = _RelMetaHelper(
        (
            "Refutes",
            [
                "confidence_score",
                "reasoning_summary",
                "evidence_item_id",
            ],  # Added evidence_item_id
            "Evidence refutes claim/argument - look for 'refutes', 'disproves', 'contradicts', 'undermines'.",
        )
    )
    CHALLENGES = _RelMetaHelper(
        (
            "Challenges",
            ["argument_summary", "basis_of_challenge"],  # Added basis_of_challenge
            "Challenges evidence/claim - 'challenges', 'disputes', 'questions the validity o'.",
        )
    )
    CONTRADICTS = _RelMetaHelper(
        (
            "Contradicts",
            [
                "confidence_score",
                "contradiction_description",
                "conflicting_item_ids",
            ],  # Added item_ids
            "Evidence contradicts other evidence - conflicting statements or facts.",
        )
    )

    # Citations and References
    CITES = _RelMetaHelper(
        (
            "Cites",
            [
                "citation_text",
                "cited_authority_type",
            ],  # Added citation_text, cited_authority_type
            "Document cites legal precedent/statute - 'cites', 'references case', 'pursuant to'.",
        )
    )
    REFERENCES = _RelMetaHelper(
        (
            "References",
            [
                "referenced_document_id",
                "reference_context",
            ],  # Added referenced_document_id
            "References another document/entity - 'see attached', 'as referenced in', cross-references.",
        )
    )

    # Procedural Relationships
    CHAIN_OF_CUSTODY = _RelMetaHelper(
        (
            "Chain_Of_Custody",
            [
                "handler_name",
                "previous_handler_name",
                "transfer_timestamp",
                "transfer_method",
                "evidence_item_id",
            ],  # Added evidence_item_id
            "Evidence custody transfer - tracking who handled evidence when and how.",
        )
    )
    PARTICIPATED_IN = _RelMetaHelper(
        (
            "Participated_In",
            ["role_in_event", "event_id"],  # Added event_id
            "Entity participated in event - 'attended', 'participated in', 'was present at'.",
        )
    )
    OCCURRED_AT = _RelMetaHelper(
        (
            "Occurred_At",
            ["location_name", "event_date", "event_id"],  # Added event_id
            "Event occurred at location - 'took place at', 'occurred at', 'happened in'.",
        )
    )
    OCCURRED_ON = _RelMetaHelper(
        (
            "Occurred_On",
            ["specific_date", "event_id"],  # Added event_id
            "Event occurred on date - temporal relationships, 'on the date o', 'occurred on'.",
        )
    )

    # Legal Actions and Proceedings
    CHARGED_WITH = _RelMetaHelper(
        (
            "Charged_With",
            [
                "charge_date",
                "offense_description",
                "indictment_count_id",
            ],  # Added indictment_count_id
            "Person charged with offense - 'charged with', 'accused o', 'indicted for'.",
        )
    )
    DISMISSED_BY = _RelMetaHelper(
        (
            "Dismissed_By",
            [
                "dismissal_date",
                "reason_for_dismissal",
                "authority_name",
            ],  # Added reason, authority
            "Charge/case dismissed by authority - 'dismissed', 'dropped charges', 'case closed'.",
        )
    )
    PLEADS_TO = _RelMetaHelper(
        (
            "Pleads_To",
            ["plea_date", "plea_type", "charge_description"],  # Added plea_type
            "Person pleads to charge - 'pleads guilty', 'pleads not guilty', 'enters plea'.",
        )
    )
    SANCTIONED_BY = _RelMetaHelper(
        (
            "Sanctioned_By",
            [
                "sanction_date",
                "reason_for_sanction",
                "imposing_authority_name",
                "sanction_details",
            ],  # Added sanction_details
            "Person sanctioned by authority - disciplinary actions, penalties, punishments.",
        )
    )

    # Testimony and Statements
    GAVE_STATEMENT = _RelMetaHelper(
        (
            "Gave_Statement",
            [
                "statement_date",
                "under_oath_status",
                "location_of_statement",
                "statement_id",
            ],  # Added statement_id
            "Witness gave statement - 'testified', 'stated under oath', 'deposed'.",
        )
    )
    STATEMENT_IN = _RelMetaHelper(
        (
            "Statement_In",
            ["case_id_reference", "hearing_id_reference"],  # Added specific references
            "Links statement to case/hearing - contextual relationship of testimony.",
        )
    )
    WITNESS_IN = _RelMetaHelper(
        (
            "Witness_In",
            [
                "event_date_witnessed",
                "relevance_to_case",
                "case_id_reference",
            ],  # Clarified attributes
            "Person witnessed event/case - 'witnessed', 'observed', 'was present during'.",
        )
    )

    # Verdict and Resolution
    FOUND_GUILTY_OF = _RelMetaHelper(
        (
            "Found_Guilty_O",
            [
                "verdict_date",
                "charge_description",
                "sentencing_details",
            ],  # Added sentencing_details
            "Person found guilty - 'found guilty', 'convicted o', 'verdict of guilty'.",
        )
    )
    FOUND_NOT_GUILTY_OF = _RelMetaHelper(
        (
            "Found_Not_Guilty_O",
            [
                "verdict_date",
                "charge_description",
                "reason_for_acquittal",
            ],  # Added reason
            "Person found not guilty - 'acquitted', 'found not guilty', 'verdict of not guilty'.",
        )
    )
    APPEALED_TO = _RelMetaHelper(
        (
            "Appealed_To",
            [
                "appeal_date",
                "appellate_court_name",
                "grounds_for_appeal",
            ],  # Added grounds
            "Case appealed to higher court - 'appealed to', 'petition for review', 'appellate court'.",
        )
    )

    # Task and Assignment
    HAS_TASK = _RelMetaHelper(
        (
            "Has_Task",
            ["assignment_date", "task_status", "task_id"],  # Added task_id
            "Case/entity has associated task - court orders, deadlines, required actions.",
        )
    )
    ASSIGNED_TO = _RelMetaHelper(
        (
            "Assigned_To",
            ["assignee_name", "task_id"],  # Added task_id
            "Task assigned to person/entity - 'assigned to', 'responsibility o', 'delegated to'.",
        )
    )

    # General Relationships
    RELATED_TO = _RelMetaHelper(
        (
            "Related_To",
            ["relationship_nature", "description_of_relation"],  # Clarified attributes
            "Generic relationship - any connection not covered by specific relationship types.",
        )
    )
    REPRESENTS = _RelMetaHelper(
        (
            "Represents",
            [
                "client_name",
                "case_id_reference",
                "representation_start_date",
            ],  # From memory_management.md
            "Legal counsel represents a client in a case.",
        )
    )
    PART_OF = _RelMetaHelper(
        (
            "Part_O",
            ["parent_entity_id", "child_entity_id", "containment_type"],
            "Indicates a part-whole relationship, e.g., a paragraph is part of a document.",
        )
    )

    def __str__(self) -> str:
        return self.value.label

    @property
    def properties(self) -> List[str]:
        return self.value.properties

    @property
    def prompt_hint(self) -> str:
        return self.value.prompt_hint

    @classmethod
    def validate_props(
        cls, rel_type_enum_val: "LegalRelationshipType", props: Dict[str, Any]
    ) -> bool:  # Corrected type hint
        """Validate that a relationship has all required properties."""
        # Similar to EntityType, consider if all properties are truly "required".
        required_props = rel_type_enum_val.properties
        if not required_props:  # If no properties are defined as required, it's valid.
            return True
        missing = [p for p in required_props if p not in props]
        if missing:
            # logger.warning(f"Relationship type {rel_type_enum_val.value.label} is missing properties: {missing}")
            return False
        return True


def get_entity_types_for_prompt() -> str:
    """Generate prompt-friendly list of entity types with extraction guidance."""
    lines = []
    for entity_type in LegalEntityType:
        attrs_str = (
            ", ".join(entity_type.attributes) if entity_type.attributes else "none"
        )
        lines.append(
            f"- {entity_type.value.label}: {{{attrs_str}}}  # {entity_type.prompt_hint}"
        )
    return "\n".join(lines)


def get_relationship_types_for_prompt() -> str:
    """Generate prompt-friendly list of relationship types with extraction guidance."""
    lines = []
    for rel_type in LegalRelationshipType:
        props_str = ", ".join(rel_type.properties) if rel_type.properties else "none"
        lines.append(
            f"- {rel_type.value.label}: {{{props_str}}}  # {rel_type.prompt_hint}"
        )
    return "\n".join(lines)


def get_extraction_prompt() -> str:
    """Generate comprehensive extraction prompt for LLM."""
    return """
LEGAL ENTITY AND RELATIONSHIP EXTRACTION GUIDELINES:

ENTITY TYPES:
{get_entity_types_for_prompt()}

RELATIONSHIP TYPES:
{get_relationship_types_for_prompt()}

EXTRACTION INSTRUCTIONS:
1. Identify entities and relationships based on the types and hints provided.
2. For each entity, extract all specified attributes.
3. For each relationship, identify source and target entities and extract all specified properties.
4. Use the prompt hints to understand the context for extraction.
5. Aim for high confidence (e.g., >0.7) and legal accuracy.
6. Preserve exact spellings for names, dates, and legal citations.
7. Note jurisdictional information and temporal sequences when relevant.
8. If an attribute or property is not present in the text, it can be omitted or marked as null.
"""


def prompt_lines_for_enum(types: Iterable[Enum]) -> str:  # Renamed and generalized
    """Generate prompt lines for a list of entity or relationship types."""
    lines = []
    for t_enum_val in types:
        meta_val = t_enum_val.value  # Access the EntityMeta or RelMeta tuple
        label = meta_val.label
        prompt_hint_val = meta_val.prompt_hint

        if hasattr(meta_val, "attributes"):  # Entity type
            elements = meta_val.attributes
        elif hasattr(meta_val, "properties"):  # Relationship type
            elements = meta_val.properties
        else:
            elements = []

        elements_str = ", ".join(elements) if elements else "none"
        lines.append(f"- {label}: {{{elements_str}}}  # {prompt_hint_val}")
    return "\n".join(lines)


def validate_entity_attributes(
    entity_type_enum_val: LegalEntityType, attributes: Dict[str, Any]
) -> bool:
    """Validate that an entity has all attributes defined in its EntityMeta."""
    # This function now checks if all attributes provided in the 'attributes' dict
    # are known for the given entity_type_enum_val. It does not enforce that all
    # defined attributes for an entity type MUST be present, as some might be optional.
    # If strict enforcement of all defined attributes is needed, the logic would change.
    defined_attrs = set(entity_type_enum_val.attributes)
    provided_attrs = set(attributes.keys())

    unknown_attrs = provided_attrs - defined_attrs
    if unknown_attrs:
        # logger.warning(f"Entity {entity_type_enum_val.value.label} has unknown attributes: {unknown_attrs}")
        return False  # Or handle as a less severe issue depending on requirements
    return True


def validate_relationship_properties(
    rel_type_enum_val: LegalRelationshipType, properties: Dict[str, Any]
) -> bool:
    """Validate that a relationship has all properties defined in its RelMeta."""
    defined_props = set(rel_type_enum_val.properties)
    if not defined_props and not properties:  # No properties defined, none provided: OK
        return True
    if (
        not defined_props and properties
    ):  # No properties defined, but some provided: potentially an issue or allow extra
        # logger.warning(f"Relationship {rel_type_enum_val.value.label} has extra properties: {properties.keys()}")
        return True  # Allow extra properties for now

    provided_props = set(properties.keys())
    unknown_props = provided_props - defined_props
    if unknown_props:
        # logger.warning(f"Relationship {rel_type_enum_val.value.label} has unknown properties: {unknown_props}")
        return False
    return True


# Convenience mappings for quick lookup
ENTITY_TYPE_MAPPING: Dict[str, LegalEntityType] = {
    et.value.label: et for et in LegalEntityType
}
RELATIONSHIP_TYPE_MAPPING: Dict[str, LegalRelationshipType] = {
    rt.value.label: rt for rt in LegalRelationshipType
}


def get_entity_type_by_label(
    label: str,
) -> Optional[LegalEntityType]:  # Return Optional
    """Get entity type by its label string."""
    return ENTITY_TYPE_MAPPING.get(label)


def get_relationship_type_by_label(
    label: str,
) -> Optional[LegalRelationshipType]:  # Return Optional
    """Get relationship type by its label string."""
    return RELATIONSHIP_TYPE_MAPPING.get(label)
