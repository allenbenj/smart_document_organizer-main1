"""
File-Level Action Generator

Generates intelligent, per-file actions based on extracted metadata.
Replaces generic pattern-based actions with precise, content-aware operations.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of file actions"""
    MOVE = "move"
    RENAME = "rename"
    COPY = "copy"
    TAG = "tag"
    ARCHIVE = "archive"


class ActionStatus(Enum):
    """Status of an action"""
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class FileAction:
    """Represents a single file action"""
    action_id: str
    action_type: ActionType
    source_path: Path
    target_path: Optional[Path] = None
    new_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: ActionStatus = ActionStatus.QUEUED
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    executed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "source_path": str(self.source_path),
            "target_path": str(self.target_path) if self.target_path else None,
            "new_name": self.new_name,
            "metadata": self.metadata,
            "status": self.status.value,
            "error": self.error,
            "created_at": self.created_at,
            "executed_at": self.executed_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileAction':
        """Create from dictionary"""
        return cls(
            action_id=data["action_id"],
            action_type=ActionType(data["action_type"]),
            source_path=Path(data["source_path"]),
            target_path=Path(data["target_path"]) if data.get("target_path") else None,
            new_name=data.get("new_name"),
            metadata=data.get("metadata", {}),
            status=ActionStatus(data.get("status", "queued")),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            executed_at=data.get("executed_at")
        )


class ActionQueue:
    """Manages queued file actions"""
    
    def __init__(self):
        self.actions: List[FileAction] = []
        self._action_map: Dict[str, FileAction] = {}
    
    def add(self, action: FileAction) -> None:
        """Add action to queue"""
        self.actions.append(action)
        self._action_map[action.action_id] = action
        logger.debug(f"Added action {action.action_id}: {action.action_type.value} {action.source_path}")
    
    def get(self, action_id: str) -> Optional[FileAction]:
        """Get action by ID"""
        return self._action_map.get(action_id)
    
    def remove(self, action_id: str) -> bool:
        """Remove action from queue"""
        action = self._action_map.pop(action_id, None)
        if action:
            self.actions.remove(action)
            return True
        return False
    
    def get_by_status(self, status: ActionStatus) -> List[FileAction]:
        """Get all actions with given status"""
        return [a for a in self.actions if a.status == status]
    
    def clear(self) -> None:
        """Clear all actions"""
        self.actions.clear()
        self._action_map.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert queue to dictionary"""
        return {
            "total_actions": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
            "by_status": {
                status.value: len(self.get_by_status(status))
                for status in ActionStatus
            }
        }
    
    def __len__(self) -> int:
        return len(self.actions)
    
    def __iter__(self):
        return iter(self.actions)


class FileLevelActionGenerator:
    """
    Generates intelligent file-level actions based on extracted metadata.
    
    This class analyzes each file individually, extracts metadata using
    LLM and regex patterns, generates precise target paths, and queues
    explicit actions for reliable execution.
    """
    
    def __init__(
        self,
        learning_engine: Optional[Any] = None,
        content_extractor: Optional[Any] = None,
        path_generator: Optional[Any] = None,
        llm_enabled: bool = True,
        preview_mode: bool = False
    ):
        """
        Initialize the action generator.
        
        Args:
            learning_engine: LearningEngine instance for pattern refinement
            content_extractor: ContentExtractor for reading file content
            path_generator: PathGenerator for creating target paths
            llm_enabled: Whether to use LLM for extraction
            preview_mode: If True, only generate actions without executing
        """
        self.learning_engine = learning_engine
        self.content_extractor = content_extractor
        self.path_generator = path_generator
        self.llm_enabled = llm_enabled
        self.preview_mode = preview_mode
        self.action_queue = ActionQueue()
        
        # Statistics
        self.stats = {
            "files_processed": 0,
            "actions_generated": 0,
            "actions_executed": 0,
            "actions_failed": 0,
            "llm_extractions": 0,
            "regex_fallbacks": 0
        }
        
        logger.info(f"FileLevelActionGenerator initialized (LLM: {llm_enabled}, Preview: {preview_mode})")
    
    def generate_actions(
        self,
        files: List[Path],
        base_output_path: Path,
        methodology: str = "legal",
        file_metadata: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> ActionQueue:
        """
        Generate actions for a list of files.
        
        Args:
            files: List of file paths to process
            base_output_path: Base output directory
            methodology: Organization methodology (legal, para, custom)
            file_metadata: Optional pre-extracted metadata dict keyed by file path
            
        Returns:
            ActionQueue with generated actions
        """
        logger.info(f"Generating actions for {len(files)} files using {methodology} methodology")
        
        for file_path in files:
            try:
                # Use pre-extracted metadata if available
                pre_metadata = None
                if file_metadata:
                    pre_metadata = file_metadata.get(str(file_path))
                
                self._generate_file_actions(file_path, base_output_path, methodology, pre_metadata)
                self.stats["files_processed"] += 1
            except Exception as e:
                logger.error(f"Failed to generate actions for {file_path}: {e}")
                # Create a failed action for tracking
                action = FileAction(
                    action_id=str(uuid.uuid4()),
                    action_type=ActionType.MOVE,
                    source_path=file_path,
                    status=ActionStatus.FAILED,
                    error=str(e)
                )
                self.action_queue.add(action)
        
        logger.info(f"Generated {len(self.action_queue)} actions for {self.stats['files_processed']} files")
        return self.action_queue
    
    def _generate_file_actions(
        self,
        file_path: Path,
        base_output_path: Path,
        methodology: str,
        pre_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Generate actions for a single file"""
        # Use pre-extracted metadata or extract new
        if pre_metadata:
            metadata = pre_metadata
        else:
            metadata = self._extract_metadata(file_path)
        
        # Generate target path
        target_path = self._generate_target_path(
            metadata, base_output_path, methodology
        )
        
        # Generate new filename if needed
        new_name = self._generate_new_name(metadata, file_path)
        
        # Create move action if path changed
        if target_path != file_path.parent:
            action = FileAction(
                action_id=str(uuid.uuid4()),
                action_type=ActionType.MOVE,
                source_path=file_path,
                target_path=target_path / (new_name or file_path.name),
                metadata=metadata
            )
            self.action_queue.add(action)
            self.stats["actions_generated"] += 1
        
        # Create rename action if name changed
        elif new_name and new_name != file_path.name:
            action = FileAction(
                action_id=str(uuid.uuid4()),
                action_type=ActionType.RENAME,
                source_path=file_path,
                new_name=new_name,
                metadata=metadata
            )
            self.action_queue.add(action)
            self.stats["actions_generated"] += 1
    
    def _extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from file using content extractor and LLM.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {
            "doc_type": None,
            "entities": {},
            "date": None,
            "case_number": None,
            "quality_score": 0.0,
            "extraction_method": "none"
        }
        
        if not self.content_extractor:
            logger.warning("No content extractor available, using filename only")
            metadata["extraction_method"] = "filename"
            return metadata
        
        try:
            # Extract content and basic metadata
            extraction_result = self.content_extractor.extract_content(file_path)
            metadata.update(extraction_result)
            
            # Try LLM extraction if enabled
            if self.llm_enabled and extraction_result.get("text"):
                try:
                    llm_entities, confidence = self.content_extractor.extract_entities_with_llm(
                        extraction_result["text"]
                    )
                    if llm_entities:
                        metadata["llm_entities"] = [
                            {"type": e.entity_type, "value": e.value, "confidence": e.confidence}
                            for e in llm_entities
                        ]
                        metadata["llm_confidence"] = confidence
                        metadata["extraction_method"] = "llm"
                        self.stats["llm_extractions"] += 1
                    else:
                        self.stats["regex_fallbacks"] += 1
                except Exception as e:
                    logger.debug(f"LLM extraction failed for {file_path}, using regex: {e}")
                    self.stats["regex_fallbacks"] += 1
            
            # Extract key fields from entities
            if "entities" in metadata:
                entities = metadata["entities"]
                if "case_number" in entities and entities["case_number"]:
                    metadata["case_number"] = entities["case_number"][0]
                if "date" in entities and entities["date"]:
                    metadata["date"] = entities["date"][0]
            
        except Exception as e:
            logger.error(f"Metadata extraction failed for {file_path}: {e}")
            metadata["extraction_method"] = "error"
            metadata["error"] = str(e)
        
        return metadata
    
    def _generate_target_path(
        self,
        metadata: Dict[str, Any],
        base_output_path: Path,
        methodology: str
    ) -> Path:
        """
        Generate target path based on metadata and methodology.
        
        Args:
            metadata: Extracted metadata
            base_output_path: Base output directory
            methodology: Organization methodology
            
        Returns:
            Target directory path
        """
        if self.path_generator:
            return self.path_generator.generate_path(
                metadata, base_output_path, methodology
            )
        
        # Fallback to simple path generation
        case = metadata.get("case_number", "Unknown_Case")
        doc_type = metadata.get("doc_type", "General")
        
        if methodology == "legal":
            return base_output_path / "01_Cases" / case / "01_Court_Filings" / doc_type
        elif methodology == "para":
            return base_output_path / "01_Projects" / doc_type
        else:
            return base_output_path / doc_type
    
    def _generate_new_name(
        self,
        metadata: Dict[str, Any],
        file_path: Path
    ) -> Optional[str]:
        """
        Generate new filename based on metadata.
        
        Args:
            metadata: Extracted metadata
            file_path: Original file path
            
        Returns:
            New filename or None if no change needed
        """
        # Only rename if quality score is low
        if metadata.get("quality_score", 1.0) >= 0.5:
            return None
        
        parts = []
        
        # Add date if available
        if metadata.get("date"):
            date_str = metadata["date"]
            # Normalize date format (simple approach)
            date_str = date_str.replace("/", "-").replace(" ", "-")
            parts.append(date_str)
        
        # Add case number if available
        if metadata.get("case_number"):
            parts.append(metadata["case_number"].replace(" ", ""))
        
        # Add document type if available
        if metadata.get("doc_type"):
            parts.append(metadata["doc_type"].capitalize())
        
        # Only generate new name if we have at least 2 components
        if len(parts) >= 2:
            return "_".join(parts) + file_path.suffix
        
        return None
    
    def get_queue_summary(self) -> Dict[str, Any]:
        """Get summary of current action queue"""
        return {
            "queue": self.action_queue.to_dict(),
            "stats": self.stats
        }
    
    def clear_queue(self) -> None:
        """Clear the action queue"""
        self.action_queue.clear()
        logger.info("Action queue cleared")
    
    def get_actions_by_file(self, file_path: Path) -> List[FileAction]:
        """Get all actions for a specific file"""
        return [
            action for action in self.action_queue
            if action.source_path == file_path
        ]
