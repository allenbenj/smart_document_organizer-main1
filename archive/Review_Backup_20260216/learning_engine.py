"""
Learning Engine - Core AI Learning System

This module implements the adaptive learning system that:
- Learns patterns from processed files
- Refines regex patterns based on success/failure
- Builds knowledge about document types and structures
- Improves over time with user feedback
"""

import json
import sqlite3
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Set
from enum import Enum

logger = logging.getLogger(__name__)


class LearningEventType(Enum):
    """Types of learning events"""
    PATTERN_MATCH = "pattern_match"
    PATTERN_MISS = "pattern_miss"
    USER_CORRECTION = "user_correction"
    STRUCTURE_FEEDBACK = "structure_feedback"
    RENAME_ACCEPTED = "rename_accepted"
    RENAME_REJECTED = "rename_rejected"
    FOLDER_CREATED = "folder_created"
    FILE_MOVED = "file_moved"


@dataclass
class LearnedPattern:
    """A pattern learned from documents"""
    pattern_id: str
    pattern_type: str  # case_number, date, entity, etc.
    regex: str
    examples: List[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    confidence: float = 0.5
    source: str = "system"  # system, learned, user
    created_at: str = ""
    updated_at: str = ""
    
    @property
    def accuracy(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        return self.success_count / total


@dataclass
class LearnedFolderStructure:
    """Knowledge about optimal folder structures"""
    structure_id: str
    document_type: str
    recommended_path: str
    naming_convention: str
    examples: List[str] = field(default_factory=list)
    usage_count: int = 0
    satisfaction_score: float = 0.5


@dataclass 
class FileNamingKnowledge:
    """Knowledge about file naming patterns"""
    knowledge_id: str
    file_type: str  # extension or document type
    naming_pattern: str  # {date}_{case}_{type}.{ext}
    components: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    success_rate: float = 0.5


class LearningDatabase:
    """SQLite database for learning storage"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize learning database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Learned patterns table
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    regex TEXT NOT NULL,
                    examples TEXT DEFAULT '[]',
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 0.5,
                    source TEXT DEFAULT 'system',
                    created_at TEXT,
                    updated_at TEXT
                );
                
                -- Learning events log
                CREATE TABLE IF NOT EXISTS learning_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    file_path TEXT,
                    pattern_id TEXT,
                    details TEXT,
                    outcome TEXT,
                    timestamp TEXT
                );
                
                -- Folder structure knowledge
                CREATE TABLE IF NOT EXISTS folder_structures (
                    structure_id TEXT PRIMARY KEY,
                    document_type TEXT NOT NULL,
                    recommended_path TEXT NOT NULL,
                    naming_convention TEXT,
                    examples TEXT DEFAULT '[]',
                    usage_count INTEGER DEFAULT 0,
                    satisfaction_score REAL DEFAULT 0.5
                );
                
                -- File naming knowledge
                CREATE TABLE IF NOT EXISTS naming_knowledge (
                    knowledge_id TEXT PRIMARY KEY,
                    file_type TEXT NOT NULL,
                    naming_pattern TEXT NOT NULL,
                    components TEXT DEFAULT '[]',
                    examples TEXT DEFAULT '[]',
                    success_rate REAL DEFAULT 0.5
                );
                
                -- LLM conversation history for context
                CREATE TABLE IF NOT EXISTS llm_context (
                    context_id TEXT PRIMARY KEY,
                    conversation_type TEXT,
                    messages TEXT,
                    insights TEXT,
                    timestamp TEXT
                );
                
                -- Entity knowledge base
                CREATE TABLE IF NOT EXISTS entity_knowledge (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT,
                    aliases TEXT DEFAULT '[]',
                    attributes TEXT DEFAULT '{}',
                    occurrences INTEGER DEFAULT 1,
                    last_seen TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_patterns_type ON learned_patterns(pattern_type);
                CREATE INDEX IF NOT EXISTS idx_events_type ON learning_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_structures_doctype ON folder_structures(document_type);
            """)
    
    def save_pattern(self, pattern: LearnedPattern):
        """Save or update a learned pattern"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO learned_patterns
                (pattern_id, pattern_type, regex, examples, success_count, 
                 failure_count, confidence, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern.pattern_id,
                pattern.pattern_type,
                pattern.regex,
                json.dumps(pattern.examples),
                pattern.success_count,
                pattern.failure_count,
                pattern.confidence,
                pattern.source,
                pattern.created_at or datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
    
    def get_patterns(self, pattern_type: Optional[str] = None) -> List[LearnedPattern]:
        """Get learned patterns, optionally filtered by type"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if pattern_type:
                rows = conn.execute(
                    "SELECT * FROM learned_patterns WHERE pattern_type = ? ORDER BY confidence DESC",
                    (pattern_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM learned_patterns ORDER BY confidence DESC"
                ).fetchall()
            
            return [
                LearnedPattern(
                    pattern_id=r['pattern_id'],
                    pattern_type=r['pattern_type'],
                    regex=r['regex'],
                    examples=json.loads(r['examples']),
                    success_count=r['success_count'],
                    failure_count=r['failure_count'],
                    confidence=r['confidence'],
                    source=r['source'],
                    created_at=r['created_at'],
                    updated_at=r['updated_at']
                )
                for r in rows
            ]
    
    def log_event(self, event_type: LearningEventType, file_path: str = None,
                  pattern_id: str = None, details: Dict = None, outcome: str = None):
        """Log a learning event"""
        import uuid
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO learning_events
                (event_id, event_type, file_path, pattern_id, details, outcome, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                event_type.value,
                file_path,
                pattern_id,
                json.dumps(details or {}),
                outcome,
                datetime.now().isoformat()
            ))
    
    def save_folder_structure(self, structure: LearnedFolderStructure):
        """Save folder structure knowledge"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO folder_structures
                (structure_id, document_type, recommended_path, naming_convention,
                 examples, usage_count, satisfaction_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                structure.structure_id,
                structure.document_type,
                structure.recommended_path,
                structure.naming_convention,
                json.dumps(structure.examples),
                structure.usage_count,
                structure.satisfaction_score
            ))
    
    def get_folder_structure(self, document_type: str) -> Optional[LearnedFolderStructure]:
        """Get recommended folder structure for document type"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM folder_structures WHERE document_type = ?",
                (document_type,)
            ).fetchone()
            
            if row:
                return LearnedFolderStructure(
                    structure_id=row['structure_id'],
                    document_type=row['document_type'],
                    recommended_path=row['recommended_path'],
                    naming_convention=row['naming_convention'],
                    examples=json.loads(row['examples']),
                    usage_count=row['usage_count'],
                    satisfaction_score=row['satisfaction_score']
                )
            return None


class LearningEngine:
    """
    Core learning engine that adapts to files and improves organization.
    
    Uses DeepSeek LLM to:
    - Analyze documents and learn patterns
    - Refine regex patterns based on successes/failures
    - Suggest folder structures
    - Generate intelligent file names
    - Continuously improve with feedback
    """
    
    def __init__(
        self,
        db_path: Path,
        model_config: Optional[Any] = None,
        llm_enabled: bool = True
    ):
        """
        Initialize the learning engine.
        
        Args:
            db_path: Path to learning database
            model_config: ModelConfig for LLM (DeepSeek)
            llm_enabled: Whether to use LLM for learning
        """
        self.db = LearningDatabase(db_path)
        self.model_config = model_config
        self.llm_enabled = llm_enabled and model_config is not None
        self._model = None
        
        # Initialize default patterns
        self._init_default_patterns()
        
        logger.info(f"Learning Engine initialized (LLM: {self.llm_enabled})")
    
    def _init_default_patterns(self):
        """Initialize with default legal document patterns"""
        default_patterns = [
            LearnedPattern(
                pattern_id="case_number_federal",
                pattern_type="case_number",
                regex=r"\b(\d{1,2})[:-]([A-Z]{2,3})[:-](\d{3,5})\b",
                examples=["22-CV-1234", "23-CR-567", "1:23-cv-00456"],
                confidence=0.9,
                source="system"
            ),
            LearnedPattern(
                pattern_id="case_number_state",
                pattern_type="case_number",
                regex=r"\b([A-Z]{1,3})\s*(\d{2,4})[-\s](\d{4,6})\b",
                examples=["CV 2023-12345", "CR2022-001234"],
                confidence=0.85,
                source="system"
            ),
            LearnedPattern(
                pattern_id="date_standard",
                pattern_type="date",
                regex=r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b",
                examples=["January 15, 2024", "March 1 2023"],
                confidence=0.95,
                source="system"
            ),
            LearnedPattern(
                pattern_id="date_numeric",
                pattern_type="date",
                regex=r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b",
                examples=["01/15/2024", "1-15-24"],
                confidence=0.8,
                source="system"
            ),
            LearnedPattern(
                pattern_id="judge_name",
                pattern_type="entity",
                regex=r"(?:Judge|Justice|Hon\.?|Honorable)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)",
                examples=["Judge Sarah Williams", "Hon. John Smith"],
                confidence=0.85,
                source="system"
            ),
        ]
        
        # Only add if not already in database
        existing = {p.pattern_id for p in self.db.get_patterns()}
        for pattern in default_patterns:
            if pattern.pattern_id not in existing:
                pattern.created_at = datetime.now().isoformat()
                self.db.save_pattern(pattern)
    
    def _get_model(self):
        """Get or initialize the LLM model"""
        if not self.llm_enabled:
            return None
            
        if self._model is None:
            from file_organizer.models.openai_model import OpenAIModel
            self._model = OpenAIModel(self.model_config)
            self._model.initialize()
        
        return self._model
    
    def learn_from_file(
        self,
        file_path: Path,
        content: str,
        extraction_result: Dict[str, Any],
        user_corrections: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Learn from a processed file.
        
        This analyzes the file, what was extracted, and any user corrections
        to improve future processing.
        
        Args:
            file_path: Path to the file
            content: File content
            extraction_result: What was extracted by current patterns
            user_corrections: Any corrections the user made
            
        Returns:
            Learning insights and suggested improvements
        """
        insights = {
            "patterns_updated": [],
            "new_patterns": [],
            "structure_suggestions": [],
            "naming_suggestions": [],
            "confidence_updates": []
        }
        
        # Log the learning event
        self.db.log_event(
            LearningEventType.FILE_MOVED if not user_corrections 
            else LearningEventType.USER_CORRECTION,
            file_path=str(file_path),
            details={
                "extraction": extraction_result,
                "corrections": user_corrections
            }
        )
        
        # If user made corrections, learn from them
        if user_corrections:
            self._learn_from_corrections(
                content, extraction_result, user_corrections, insights
            )
        
        # Use LLM to analyze and suggest improvements
        if self.llm_enabled:
            llm_insights = self._analyze_with_llm(
                file_path, content, extraction_result
            )
            insights.update(llm_insights)
        
        # Update pattern confidences based on results
        self._update_pattern_confidence(extraction_result)
        
        return insights
    
    def _learn_from_corrections(
        self,
        content: str,
        extraction: Dict,
        corrections: Dict,
        insights: Dict
    ):
        """Learn from user corrections to improve patterns"""
        import re
        import uuid
        
        # Check what was missed or wrong
        for field, correct_value in corrections.items():
            extracted_value = extraction.get(field)
            
            if extracted_value != correct_value:
                # Pattern missed or got wrong value
                # Try to create a new pattern for this
                if correct_value and correct_value in content:
                    # Find context around the correct value
                    idx = content.find(correct_value)
                    context_start = max(0, idx - 50)
                    context_end = min(len(content), idx + len(correct_value) + 50)
                    context = content[context_start:context_end]
                    
                    # Use LLM to suggest a regex pattern
                    if self.llm_enabled:
                        new_pattern = self._generate_pattern_with_llm(
                            field, correct_value, context
                        )
                        if new_pattern:
                            new_pattern.pattern_id = f"learned_{field}_{uuid.uuid4().hex[:8]}"
                            new_pattern.source = "learned"
                            self.db.save_pattern(new_pattern)
                            insights["new_patterns"].append(new_pattern.pattern_id)
                    
                    # Mark existing patterns as less reliable
                    existing_patterns = self.db.get_patterns(field)
                    for pattern in existing_patterns:
                        pattern.failure_count += 1
                        pattern.confidence = pattern.accuracy * 0.9  # Decay
                        self.db.save_pattern(pattern)
                        insights["confidence_updates"].append({
                            "pattern_id": pattern.pattern_id,
                            "new_confidence": pattern.confidence
                        })
    
    def _generate_pattern_with_llm(
        self,
        field_type: str,
        value: str,
        context: str
    ) -> Optional[LearnedPattern]:
        """Use LLM to generate a regex pattern for a value"""
        model = self._get_model()
        if not model:
            return None
        
        prompt = f"""You are a regex pattern expert. Generate a Python regex pattern to match values like the one shown.

Field Type: {field_type}
Value to Match: {value}
Context: {context}

Requirements:
1. The pattern should be general enough to match similar values
2. Use named groups if appropriate
3. Include word boundaries (\\b) where needed
4. Make it robust to minor variations

Respond with ONLY a JSON object:
{{
    "regex": "your_regex_pattern_here",
    "explanation": "brief explanation",
    "examples": ["example1", "example2", "example3"]
}}
"""
        
        try:
            response = model.generate(prompt)
            data = json.loads(response)
            
            # Validate the regex
            import re
            re.compile(data["regex"])
            
            return LearnedPattern(
                pattern_id="",  # Will be set by caller
                pattern_type=field_type,
                regex=data["regex"],
                examples=data.get("examples", [value]),
                confidence=0.7,  # Start with moderate confidence
                created_at=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to generate pattern with LLM: {e}")
            return None
    
    def _analyze_with_llm(
        self,
        file_path: Path,
        content: str,
        extraction: Dict
    ) -> Dict[str, Any]:
        """Use LLM to analyze file and suggest improvements"""
        model = self._get_model()
        if not model:
            return {}
        
        # Get current patterns for context
        patterns = self.db.get_patterns()
        pattern_summary = [
            f"- {p.pattern_type}: {p.regex} (confidence: {p.confidence:.0%})"
            for p in patterns[:10]
        ]
        
        prompt = f"""You are an expert file organization AI. Analyze this document and provide insights.

File: {file_path.name}
Current Extraction Results: {json.dumps(extraction, indent=2)}

Current Patterns:
{chr(10).join(pattern_summary)}

Document Content (first 3000 chars):
---
{content[:3000]}
---

Analyze and respond with JSON:
{{
    "document_type": "type of document",
    "key_entities": ["entity1", "entity2"],
    "suggested_folder": "recommended/folder/path",
    "suggested_filename": "recommended_filename.ext",
    "naming_components": ["date", "case_number", "type"],
    "missing_patterns": ["patterns that should exist but don't"],
    "pattern_improvements": [
        {{"pattern_type": "type", "suggestion": "improvement"}}
    ],
    "confidence": 0.0-1.0
}}
"""
        
        try:
            response = model.generate(prompt)
            data = json.loads(response)
            
            return {
                "llm_analysis": data,
                "structure_suggestions": [data.get("suggested_folder", "")],
                "naming_suggestions": [data.get("suggested_filename", "")]
            }
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {}
    
    def _update_pattern_confidence(self, extraction: Dict):
        """Update pattern confidences based on extraction results"""
        patterns = self.db.get_patterns()
        
        for pattern in patterns:
            # Check if this pattern type had a result
            if pattern.pattern_type in extraction:
                value = extraction[pattern.pattern_type]
                if value:
                    pattern.success_count += 1
                else:
                    pattern.failure_count += 1
                
                # Recalculate confidence with smoothing
                pattern.confidence = (
                    (pattern.success_count + 1) / 
                    (pattern.success_count + pattern.failure_count + 2)
                )
                self.db.save_pattern(pattern)
    
    def suggest_folder_structure(
        self,
        document_type: str,
        entities: Dict[str, Any],
        existing_structure: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Suggest optimal folder structure for a document.
        
        Args:
            document_type: Type of document (motion, order, etc.)
            entities: Extracted entities (case_number, date, etc.)
            existing_structure: Current folder structure root
            
        Returns:
            Folder structure suggestion
        """
        # Check if we have learned structure for this type
        learned = self.db.get_folder_structure(document_type)
        
        suggestion = {
            "path": "",
            "create_folders": [],
            "reasoning": [],
            "confidence": 0.5
        }
        
        if learned and learned.satisfaction_score > 0.7:
            # Use learned structure
            suggestion["path"] = learned.recommended_path
            suggestion["reasoning"].append(f"Using learned structure (satisfaction: {learned.satisfaction_score:.0%})")
            suggestion["confidence"] = learned.satisfaction_score
        elif self.llm_enabled:
            # Ask LLM to suggest structure
            suggestion = self._suggest_structure_with_llm(
                document_type, entities, existing_structure
            )
        else:
            # Use rule-based default
            suggestion = self._default_folder_suggestion(document_type, entities)
        
        return suggestion
    
    def _suggest_structure_with_llm(
        self,
        document_type: str,
        entities: Dict,
        existing_structure: Optional[Path]
    ) -> Dict[str, Any]:
        """Use LLM to suggest folder structure"""
        model = self._get_model()
        if not model:
            return self._default_folder_suggestion(document_type, entities)
        
        # Get existing folder structure if available
        existing_folders = []
        if existing_structure and existing_structure.exists():
            existing_folders = [
                str(p.relative_to(existing_structure))
                for p in existing_structure.rglob("*")
                if p.is_dir()
            ][:20]
        
        prompt = f"""You are a file organization expert. Suggest the optimal folder structure.

Document Type: {document_type}
Extracted Entities: {json.dumps(entities, indent=2)}

Existing Folders:
{chr(10).join(existing_folders) if existing_folders else "None yet"}

Requirements:
1. Create a logical, navigable hierarchy
2. Use clear, descriptive folder names
3. Consider the document lifecycle
4. Group related documents together
5. Use numbered prefixes for ordering (01_, 02_, etc.)

Respond with JSON:
{{
    "recommended_path": "Cases/CaseNumber/DocumentType",
    "folders_to_create": ["folder1", "folder2"],
    "naming_convention": "description of naming",
    "reasoning": ["reason1", "reason2"],
    "confidence": 0.0-1.0
}}
"""
        
        try:
            response = model.generate(prompt)
            data = json.loads(response)
            
            return {
                "path": data.get("recommended_path", ""),
                "create_folders": data.get("folders_to_create", []),
                "naming_convention": data.get("naming_convention", ""),
                "reasoning": data.get("reasoning", []),
                "confidence": data.get("confidence", 0.7)
            }
        except Exception as e:
            logger.error(f"LLM structure suggestion failed: {e}")
            return self._default_folder_suggestion(document_type, entities)
    
    def _default_folder_suggestion(
        self,
        document_type: str,
        entities: Dict
    ) -> Dict[str, Any]:
        """Default rule-based folder suggestion"""
        case_number = entities.get("case_number", "Unknown_Case")
        
        # Map document types to folders
        type_folders = {
            "motion": "01_Court_Record/Motions",
            "order": "01_Court_Record/Orders",
            "brief": "04_Research/Briefs",
            "discovery": "02_Discovery",
            "evidence": "03_Evidence",
            "correspondence": "06_Correspondence",
            "memo": "05_Analysis/Memos",
            "contract": "Legal_Documents/Contracts",
        }
        
        folder = type_folders.get(document_type.lower(), "07_Working")
        
        return {
            "path": f"Cases/{case_number}/{folder}",
            "create_folders": [f"Cases/{case_number}", f"Cases/{case_number}/{folder}"],
            "reasoning": ["Default structure based on document type"],
            "confidence": 0.6
        }
    
    def suggest_filename(
        self,
        file_path: Path,
        content: str,
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Suggest an intelligent filename.
        
        Args:
            file_path: Current file path
            content: File content
            entities: Extracted entities
            
        Returns:
            Filename suggestion with components
        """
        original_name = file_path.name
        extension = file_path.suffix
        
        suggestion = {
            "original": original_name,
            "suggested": original_name,
            "components": [],
            "reasoning": [],
            "confidence": 0.5
        }
        
        if self.llm_enabled:
            suggestion = self._suggest_filename_with_llm(
                file_path, content, entities
            )
        else:
            suggestion = self._default_filename_suggestion(
                file_path, entities
            )
        
        return suggestion
    
    def _suggest_filename_with_llm(
        self,
        file_path: Path,
        content: str,
        entities: Dict
    ) -> Dict[str, Any]:
        """Use LLM to suggest filename"""
        model = self._get_model()
        if not model:
            return self._default_filename_suggestion(file_path, entities)
        
        prompt = f"""You are a file naming expert. Suggest an optimal filename.

Current Filename: {file_path.name}
File Extension: {file_path.suffix}
Extracted Entities: {json.dumps(entities, indent=2)}

Document Preview (first 1000 chars):
---
{content[:1000]}
---

Requirements:
1. Use clear, descriptive naming
2. Include key identifiers (date, case number, type)
3. Use underscores or hyphens, no spaces
4. Keep it reasonably short (<100 chars)
5. Preserve the file extension
6. Make it sortable (dates in YYYY-MM-DD format)

Respond with JSON:
{{
    "suggested_filename": "YYYY-MM-DD_CaseNumber_DocumentType.ext",
    "components": ["date", "case_number", "document_type"],
    "reasoning": ["reason1", "reason2"],
    "confidence": 0.0-1.0
}}
"""
        
        try:
            response = model.generate(prompt)
            data = json.loads(response)
            
            return {
                "original": file_path.name,
                "suggested": data.get("suggested_filename", file_path.name),
                "components": data.get("components", []),
                "reasoning": data.get("reasoning", []),
                "confidence": data.get("confidence", 0.7)
            }
        except Exception as e:
            logger.error(f"LLM filename suggestion failed: {e}")
            return self._default_filename_suggestion(file_path, entities)
    
    def _default_filename_suggestion(
        self,
        file_path: Path,
        entities: Dict
    ) -> Dict[str, Any]:
        """Default rule-based filename suggestion"""
        ext = file_path.suffix
        components = []
        parts = []
        
        # Add date if available
        if "date" in entities and entities["date"]:
            date_str = entities["date"]
            # Try to normalize to YYYY-MM-DD
            parts.append(date_str.replace("/", "-"))
            components.append("date")
        
        # Add case number if available
        if "case_number" in entities and entities["case_number"]:
            parts.append(entities["case_number"].replace(" ", "_"))
            components.append("case_number")
        
        # Add document type if available
        if "document_type" in entities and entities["document_type"]:
            parts.append(entities["document_type"].replace(" ", "_"))
            components.append("document_type")
        
        if parts:
            suggested = "_".join(parts) + ext
        else:
            suggested = file_path.name
        
        return {
            "original": file_path.name,
            "suggested": suggested,
            "components": components,
            "reasoning": ["Default naming based on extracted entities"],
            "confidence": 0.5
        }
    
    def get_active_patterns(self, min_confidence: float = 0.6) -> List[LearnedPattern]:
        """Get patterns above confidence threshold"""
        patterns = self.db.get_patterns()
        return [p for p in patterns if p.confidence >= min_confidence]
    
    def record_feedback(
        self,
        file_path: Path,
        feedback_type: str,
        accepted: bool,
        details: Optional[Dict] = None
    ):
        """
        Record user feedback to improve learning.
        
        Args:
            file_path: File the feedback is about
            feedback_type: "rename", "move", "structure"
            accepted: Whether user accepted the suggestion
            details: Additional details
        """
        event_type = {
            "rename": LearningEventType.RENAME_ACCEPTED if accepted 
                      else LearningEventType.RENAME_REJECTED,
            "move": LearningEventType.FILE_MOVED,
            "structure": LearningEventType.STRUCTURE_FEEDBACK,
        }.get(feedback_type, LearningEventType.USER_CORRECTION)
        
        self.db.log_event(
            event_type,
            file_path=str(file_path),
            details=details,
            outcome="accepted" if accepted else "rejected"
        )
        
        # Update satisfaction scores for structures
        if feedback_type == "structure" and details:
            doc_type = details.get("document_type")
            if doc_type:
                structure = self.db.get_folder_structure(doc_type)
                if structure:
                    # Adjust satisfaction score
                    if accepted:
                        structure.satisfaction_score = min(1.0, 
                            structure.satisfaction_score * 1.1)
                    else:
                        structure.satisfaction_score = max(0.0,
                            structure.satisfaction_score * 0.9)
                    structure.usage_count += 1
                    self.db.save_folder_structure(structure)
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics about learning progress"""
        patterns = self.db.get_patterns()
        
        return {
            "total_patterns": len(patterns),
            "learned_patterns": len([p for p in patterns if p.source == "learned"]),
            "system_patterns": len([p for p in patterns if p.source == "system"]),
            "high_confidence_patterns": len([p for p in patterns if p.confidence >= 0.8]),
            "average_confidence": sum(p.confidence for p in patterns) / len(patterns) if patterns else 0,
            "pattern_types": list(set(p.pattern_type for p in patterns)),
        }
    
    def cleanup(self):
        """Cleanup resources"""
        if self._model:
            self._model.cleanup()
            self._model = None
