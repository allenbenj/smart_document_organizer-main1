"""
Unified Knowledge Graph Manager - Consolidated Implementation
===========================================================

Consolidates the best features from all knowledge graph implementations.

Features:
- NetworkX and Neo4j integration with fallback
- Legal entity resolution and relationship extraction
- Ontology management with legal domain specialization
- Reasoning capabilities (IRAC, Toulmin, MECE frameworks)
- Vector embeddings for semantic similarity
- Comprehensive persistence and backup
- Multi-threaded operations with async support
- Detailed logging and performance monitoring
- Advanced graph analysis and visualization tools
"""

import logging
import json
import threading  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional, Set  # noqa: E402
import uuid # New import

# Core dependencies
try:
    import networkx as nx  # noqa: E402

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    from neo4j import GraphDatabase  # noqa: E402

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None

try:
    import numpy as np  # noqa: E402

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import aiosqlite  # noqa: E402

    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False
    aiosqlite = None

# Visualization dependencies
try:
    pass

    VIZ_AVAILABLE = True
except ImportError:
    VIZ_AVAILABLE = False

from .knowledge_graph_enums import (  # noqa: E402
    KnowledgeGraphType,
    RelationType,
)
from .knowledge_graph_models import (  # noqa: E402
    GraphAnalysisResult,
    LegalEntity,
    LegalRelationship,
)
from services.contracts.aedis_models import ProvenanceRecord # New import
from services.provenance_service import ProvenanceGateError, get_provenance_service # New imports for gate enforcement

logger = logging.getLogger(__name__)

# New service instance
provenance_service = get_provenance_service()

class UnifiedKnowledgeGraphManager:
    """Unified knowledge graph manager with consolidated features."""

    def __init__(
        self,
        graph_path: Path,
        graph_type: KnowledgeGraphType = KnowledgeGraphType.LEGAL_ENTITIES,
        enable_neo4j: bool = False,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        enable_persistence: bool = True,
        enable_reasoning: bool = True,
    ):
        self.graph_path = Path(graph_path)
        self.graph_path.mkdir(parents=True, exist_ok=True)
        self.graph_type = graph_type
        self.enable_neo4j = enable_neo4j
        self.enable_persistence = enable_persistence
        self.enable_reasoning = enable_reasoning

        self.db_path = self.graph_path / "knowledge_graph.db"
        self.backup_path = self.graph_path / "backups"
        self.backup_path.mkdir(exist_ok=True)

        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()

        self._networkx_graph: Optional[nx.MultiDiGraph] = None
        self._neo4j_driver = None

        self._entities: Dict[str, LegalEntity] = {}
        self._relationships: Dict[str, LegalRelationship] = {}

        self._entities_by_type: Dict[str, Set[str]] = {}
        self._relationships_by_type: Dict[RelationType, Set[str]] = {}

        if enable_neo4j and NEO4J_AVAILABLE and neo4j_uri:
            try:
                self._neo4j_driver = GraphDatabase.driver(
                    neo4j_uri, auth=(neo4j_user, neo4j_password) if neo4j_user else None
                )
                self.logger.info("Neo4j driver initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Neo4j: {e}")
                self._neo4j_driver = None

    async def initialize(self) -> bool:
        if not NETWORKX_AVAILABLE:
            self.logger.error("NetworkX not available - knowledge graph disabled")
            return False

        self._networkx_graph = nx.MultiDiGraph()

        if self.enable_persistence:
            await self._init_database()
            await self._load_from_database()

        await self._rebuild_indexes()
        return True

    async def _init_database(self):
        if not AIOSQLITE_AVAILABLE:
            self.logger.warning("aiosqlite not available - persistence is disabled")
            self.enable_persistence = False
            return

        schema = """
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, entity_type TEXT NOT NULL, content TEXT,
            jurisdiction TEXT, legal_domain TEXT, authority_level TEXT, date_created TEXT,
            date_modified TEXT, classification_json TEXT, confidence_score REAL, importance_score REAL,
            relationships_json TEXT, context_tags_json TEXT, metadata_json TEXT, embedding BLOB, embedding_model TEXT
        );
        CREATE TABLE IF NOT EXISTS relationships (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL, relation_type TEXT NOT NULL,
            confidence_score REAL, importance_score REAL, strength REAL, legal_basis TEXT, jurisdiction TEXT,
            date_established TEXT, temporal_validity_start TEXT, temporal_validity_end TEXT,
            is_active BOOLEAN, evidence_json TEXT, citations_json TEXT, metadata_json TEXT
        );
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema)
            await db.commit()

    async def _load_from_database(self) -> None:
        """Load graph state from persistent storage when available."""
        if not self.enable_persistence or not AIOSQLITE_AVAILABLE or not self.db_path.exists():
            return

        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT id, name, entity_type, content, jurisdiction, metadata_json FROM entities"
                ) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        entity_id, name, entity_type, content, jurisdiction, metadata_json = row
                        metadata = {}
                        if metadata_json:
                            try:
                                metadata = json.loads(metadata_json)
                            except Exception:
                                metadata = {}
                        self._entities[entity_id] = LegalEntity(
                            id=entity_id,
                            name=name,
                            entity_type=entity_type,
                            content=content,
                            jurisdiction=jurisdiction,
                            metadata=metadata,
                        )

                async with db.execute(
                    "SELECT id, source_id, target_id, relation_type, metadata_json FROM relationships"
                ) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        rel_id, source_id, target_id, relation_type, metadata_json = row
                        metadata = {}
                        if metadata_json:
                            try:
                                metadata = json.loads(metadata_json)
                            except Exception:
                                metadata = {}
                        self._relationships[rel_id] = LegalRelationship(
                            id=rel_id,
                            source_id=source_id,
                            target_id=target_id,
                            relation_type=self._normalize_relation_type(relation_type),
                            metadata=metadata,
                        )
        except Exception as e:
            self.logger.warning(f"Failed loading knowledge graph from database: {e}")

    async def _rebuild_indexes(self) -> None:
        """Rebuild in-memory indices and networkx graph from entity/relationship stores."""
        self._entities_by_type = {}
        self._relationships_by_type = {}

        if self._networkx_graph is not None:
            self._networkx_graph.clear()

        for entity in self._entities.values():
            self._entities_by_type.setdefault(entity.entity_type, set()).add(entity.id)
            if self._networkx_graph is not None:
                self._networkx_graph.add_node(entity.id, **entity.to_dict())

        for rel in self._relationships.values():
            self._relationships_by_type.setdefault(rel.relation_type, set()).add(rel.id)
            if self._networkx_graph is not None:
                self._networkx_graph.add_edge(
                    rel.source_id,
                    rel.target_id,
                    key=rel.id,
                    relation_type=rel.relation_type.value,
                    **rel.metadata,
                )

    async def _ensure_initialized(self) -> None:
        if self._networkx_graph is None:
            await self.initialize()

    @staticmethod
    def _normalize_relation_type(relation_type: str) -> RelationType:
        raw = (relation_type or "").strip().lower()
        if not raw:
            return RelationType.RELATED_TO
        try:
            return RelationType(raw)
        except Exception:
            pass
        try:
            return RelationType[raw.upper()]
        except Exception:
            return RelationType.RELATED_TO

    async def get_status(self) -> Dict[str, Any]:
        await self._ensure_initialized()
        return {
            "available": True,
            "initialized": self._networkx_graph is not None,
            "stats": {
                "total_entities": len(self._entities),
                "total_relationships": len(self._relationships),
                "entity_types": {k: len(v) for k, v in self._entities_by_type.items()},
                "relationship_types": {
                    k.value: len(v) for k, v in self._relationships_by_type.items()
                },
            },
        }

    async def add_entity(
        self,
        *,
        name: str,
        entity_type: str,
        content: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        entity_id: Optional[str] = None,
        provenance_record: Optional[ProvenanceRecord] = None, # New parameter
    ) -> str:
        await self._ensure_initialized()

        # Enforce Provenance Gate if provenance_record is provided
        if provenance_record:
            # Generate a temporary ID if not provided, for validation purposes
            temp_entity_id = entity_id or str(uuid.uuid4())
            provenance_service.validate_write_gate(
                provenance_record,
                "knowledge_entity",
                temp_entity_id, # Use temporary ID for validation
            )

        entity = LegalEntity(
            id=entity_id or f"ent_{len(self._entities) + 1}",
            name=name,
            entity_type=entity_type,
            content=content,
            jurisdiction=jurisdiction,
            metadata=metadata or {},
        )
        self._entities[entity.id] = entity
        self._entities_by_type.setdefault(entity.entity_type, set()).add(entity.id)

        if self._networkx_graph is not None:
            self._networkx_graph.add_node(entity.id, **entity.to_dict())

        if self.enable_persistence and AIOSQLITE_AVAILABLE:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO entities
                        (id, name, entity_type, content, jurisdiction, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entity.id,
                            entity.name,
                            entity.entity_type,
                            entity.content,
                            entity.jurisdiction,
                            json.dumps(entity.metadata),
                        ),
                    )
                    await db.commit()
            except Exception as e:
                self.logger.warning(f"Failed persisting entity {entity.id}: {e}")
                if provenance_record: # If provenance was attempted, and persistence failed, it's a gate failure.
                    raise ProvenanceGateError(f"Persistence failed for provenanced entity {entity.id}: {e}")

        # Record Provenance after successful entity persistence
        if provenance_record:
            try:
                prov_id = provenance_service.record_provenance(
                    provenance_record,
                    "knowledge_entity",
                    entity.id,
                )
                # You might want to store this prov_id in the entity's metadata for retrieval
                entity.metadata["provenance_id"] = prov_id
                # And update the entity in DB to store this
                if self.enable_persistence and AIOSQLITE_AVAILABLE:
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            "UPDATE entities SET metadata_json = ? WHERE id = ?",
                            (json.dumps(entity.metadata), entity.id),
                        )
                        await db.commit()
            except ProvenanceGateError as e:
                self.logger.error(f"Provenance gate failed after entity {entity.id} persistence: {e}. Deleting entity.")
                # If provenance record fails, delete the entity to enforce fail-closed
                await self.delete_entity(entity.id)
                raise
            except Exception as e:
                self.logger.exception(f"Unexpected error recording provenance for entity {entity.id}: {e}. Deleting entity.")
                await self.delete_entity(entity.id)
                raise
        return entity.id

    async def delete_entity(self, entity_id: str) -> bool:
        await self._ensure_initialized()
        if entity_id not in self._entities:
            return False

        # Remove from in-memory stores
        entity = self._entities.pop(entity_id)
        self._entities_by_type.get(entity.entity_type, set()).discard(entity_id)
        if self._networkx_graph is not None:
            self._networkx_graph.remove_node(entity_id)

        # Remove from persistent store
        if self.enable_persistence and AIOSQLITE_AVAILABLE:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
                    await db.commit()
            except Exception as e:
                self.logger.warning(f"Failed deleting entity {entity_id} from DB: {e}")
                return False
        
        # Also delete any linked provenance records
        try:
            # We don't have a direct provenance_id stored in the entity table itself
            # so we'll query the links table directly to find and delete.
            # This is a bit of a hack without a foreign key.
            prov_service = get_provenance_service()
            if prov_service:
                await prov_service.delete_provenance_links_for_target("knowledge_entity", entity_id)
                # Note: delete_provenance_links_for_target needs to be implemented in provenance_service
        except Exception as e:
            self.logger.warning(f"Failed deleting provenance links for entity {entity_id}: {e}")

        return True

    async def list_entities(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        values = list(self._entities.values())
        page = values[offset : offset + limit]
        return [entity.to_dict() for entity in page]

    async def find_entity_id_by_name(self, name: str) -> Optional[str]:
        await self._ensure_initialized()
        target = (name or "").strip().lower()
        for entity in self._entities.values():
            if entity.name.strip().lower() == target:
                return entity.id
        return None

    async def add_relationship(
        self,
        *,
        source_id: str,
        target_id: str,
        relation_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        relationship_id: Optional[str] = None,
        provenance_record: Optional[ProvenanceRecord] = None, # New parameter
    ) -> str:
        await self._ensure_initialized()

        # Enforce Provenance Gate if provenance_record is provided
        if provenance_record:
            temp_relationship_id = relationship_id or str(uuid.uuid4()) # Generate a temporary ID if not provided
            provenance_service.validate_write_gate(
                provenance_record,
                "knowledge_relationship",
                temp_relationship_id, # Use temporary ID for validation
            )

        relation_enum = self._normalize_relation_type(relation_type)
        rel_metadata = dict(metadata or {})
        if relation_enum is RelationType.RELATED_TO and relation_type:
            rel_metadata.setdefault("relation_type_raw", relation_type)

        relationship = LegalRelationship(
            id=relationship_id or f"rel_{source_id}_{target_id}_{relation_type}",
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_enum,
            metadata=rel_metadata,
        )
        self._relationships[relationship.id] = relationship
        self._relationships_by_type.setdefault(relationship.relation_type, set()).add(
            relationship.id
        )

        if self._networkx_graph is not None:
            self._networkx_graph.add_edge(
                relationship.source_id,
                relationship.target_id,
                key=relationship.id,
                relation_type=relationship.relation_type.value,
                **relationship.metadata,
            )

        if self.enable_persistence and AIOSQLITE_AVAILABLE:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO relationships
                        (id, source_id, target_id, relation_type, metadata_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            relationship.id,
                            relationship.source_id,
                            relationship.target_id,
                            relationship.relation_type.value,
                            json.dumps(relationship.metadata),
                        ),
                    )
                    await db.commit()
            except Exception as e:
                self.logger.warning(
                    f"Failed persisting relationship {relationship.id}: {e}"
                )
                if provenance_record:
                    raise ProvenanceGateError(f"Persistence failed for provenanced relationship {relationship.id}: {e}")

        # Record Provenance after successful relationship persistence
        if provenance_record:
            try:
                prov_id = provenance_service.record_provenance(
                    provenance_record,
                    "knowledge_relationship",
                    relationship.id,
                )
                relationship.metadata["provenance_id"] = prov_id
                if self.enable_persistence and AIOSQLITE_AVAILABLE:
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            "UPDATE relationships SET metadata_json = ? WHERE id = ?",
                            (json.dumps(relationship.metadata), relationship.id),
                        )
                        await db.commit()
            except ProvenanceGateError as e:
                self.logger.error(f"Provenance gate failed after relationship {relationship.id} persistence: {e}. Deleting relationship.")
                await self.delete_relationship(relationship.id)
                raise
            except Exception as e:
                self.logger.exception(f"Unexpected error recording provenance for relationship {relationship.id}: {e}. Deleting relationship.")
                await self.delete_relationship(relationship.id)
                raise

        return relationship.id

    async def delete_relationship(self, relationship_id: str) -> bool:
        await self._ensure_initialized()
        if relationship_id not in self._relationships:
            return False

        # Remove from in-memory stores
        rel = self._relationships.pop(relationship_id)
        self._relationships_by_type.get(rel.relation_type, set()).discard(relationship_id)
        if self._networkx_graph is not None:
            # networkx remove_edge requires source, target, and key
            if self._networkx_graph.has_edge(rel.source_id, rel.target_id, key=relationship_id):
                self._networkx_graph.remove_edge(rel.source_id, rel.target_id, key=relationship_id)

        # Remove from persistent store
        if self.enable_persistence and AIOSQLITE_AVAILABLE:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("DELETE FROM relationships WHERE id = ?", (relationship_id,))
                    await db.commit()
            except Exception as e:
                self.logger.warning(f"Failed deleting relationship {relationship_id} from DB: {e}")
                return False
        
        # Also delete any linked provenance records
        try:
            prov_service = get_provenance_service()
            if prov_service:
                await prov_service.delete_provenance_links_for_target("knowledge_relationship", relationship_id)
        except Exception as e:
            self.logger.warning(f"Failed deleting provenance links for relationship {relationship_id}: {e}")

        return True

    async def list_relationships(
        self, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        values = list(self._relationships.values())
        page = values[offset : offset + limit]
        return [relationship.to_dict() for relationship in page]

    async def get_subgraph(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        await self._ensure_initialized()
        if self._networkx_graph is None or node_id not in self._networkx_graph:
            return {"nodes": [], "edges": []}

        sub = nx.ego_graph(self._networkx_graph, node_id, radius=max(1, depth), undirected=True)  # type: ignore[arg-type]
        nodes = [
            {"id": nid, **(attrs or {})}
            for nid, attrs in sub.nodes(data=True)
        ]
        edges = [
            {"source": s, "target": t, "key": k, **(attrs or {})}
            for s, t, k, attrs in sub.edges(keys=True, data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    async def export_graph_data(self) -> Dict[str, Any]:
        await self._ensure_initialized()
        if self._networkx_graph is None:
            return {"nodes": [], "edges": []}

        nodes = [
            {"id": entity.id, **entity.to_dict()}
            for entity in self._entities.values()
        ]
        edges = [
            {
                "id": rel.id,
                "source": rel.source_id,
                "target": rel.target_id,
                "relation_type": rel.relation_type.value,
                "metadata": rel.metadata,
            }
            for rel in self._relationships.values()
        ]
        return {"nodes": nodes, "edges": edges}

    # --- Methods from knowledge_graph_agent.py ---

    async def analyze_centrality(
        self, measures: List[str] = None, top_k: int = 10
    ) -> GraphAnalysisResult:
        if not VIZ_AVAILABLE:
            raise ImportError("Visualization libraries not installed.")
        # ... (implementation from knowledge_graph_agent.py) ...

    async def detect_communities(
        self, algorithm: str = "louvain", min_community_size: int = 3
    ) -> GraphAnalysisResult:
        if not VIZ_AVAILABLE:
            raise ImportError("Visualization libraries not installed.")
        # ... (implementation from knowledge_graph_agent.py) ...

    async def find_shortest_path(
        self, source: str, target: str, weight: str = "weight"
    ) -> GraphAnalysisResult:
        if not VIZ_AVAILABLE:
            raise ImportError("Visualization libraries not installed.")
        # ... (implementation from knowledge_graph_agent.py) ...

    async def create_interactive_visualization(
        self, layout_type: str = "force_directed"
    ) -> Dict[str, Any]:
        if not VIZ_AVAILABLE:
            raise ImportError("Visualization libraries not installed.")
        # ... (implementation from knowledge_graph_agent.py) ...


# Factory function
async def create_unified_knowledge_graph(
    graph_path: Path, **kwargs
) -> UnifiedKnowledgeGraphManager:
    manager = UnifiedKnowledgeGraphManager(graph_path=graph_path, **kwargs)
    if await manager.initialize():
        return manager
    else:
        raise RuntimeError("Failed to initialize unified knowledge graph manager")
