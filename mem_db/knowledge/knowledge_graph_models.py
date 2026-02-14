from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

import numpy as np  # noqa: E402

from .knowledge_graph_enums import RelationType  # noqa: E402


@dataclass
class LegalEntity:
    """Enhanced legal entity with comprehensive metadata."""

    id: str
    name: str
    entity_type: str
    content: Optional[str] = None
    jurisdiction: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None

    def to_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        if isinstance(self.embedding, np.ndarray):
            data["embedding"] = self.embedding.tolist()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LegalEntity":
        if "embedding" in data and data["embedding"] is not None:
            data["embedding"] = np.array(data["embedding"])
        return cls(**data)


@dataclass
class LegalRelationship:
    """Enhanced legal relationship with comprehensive metadata."""

    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        data["relation_type"] = self.relation_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LegalRelationship":
        data["relation_type"] = RelationType(data["relation_type"])
        return cls(**data)


@dataclass
class QueryResult:
    entities: List[LegalEntity] = field(default_factory=list)
    relationships: List[LegalRelationship] = field(default_factory=list)


@dataclass
class GraphLayout:
    layout_type: str
    positions: Dict[str, Tuple[float, float]]
    metadata: Dict[str, Any]


@dataclass
class GraphAnalysisResult:
    analysis_type: str
    results: Dict[str, Any]
    metadata: Dict[str, Any]
    visualization_data: Optional[Dict[str, Any]] = None


@dataclass
class GraphCluster:
    cluster_id: str
    nodes: List[str]
    centroid: Optional[str]
    properties: Dict[str, Any]
    coherence_score: float
