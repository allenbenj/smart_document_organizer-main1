"""
Intelligent File Renamer - Smart File Naming

This module handles intelligent file renaming by:
- Analyzing file content to extract naming components
- Learning naming patterns from user behavior
- Generating consistent, logical filenames
- Preserving important metadata in filenames
"""

import re
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from .learning_engine import LearningEngine, FileNamingKnowledge

logger = logging.getLogger(__name__)


@dataclass
class RenameProposal:
    """A proposed file rename"""
    original_path: Path
    proposed_name: str
    proposed_path: Path
    components: Dict[str, str]  # date, case_number, type, etc.
    confidence: float
    reasoning: List[str]


class IntelligentFileRenamer:
    """
    Intelligently renames files based on content and patterns.
    
    Uses LLM to:
    - Extract key metadata for naming
    - Generate descriptive, sortable filenames
    - Learn naming patterns from user preferences
    - Maintain consistency across file types
    """
    
    def __init__(
        self,
        learning_engine: LearningEngine,
        max_filename_length: int = 100
    ):
        """
        Initialize the file renamer.
        
        Args:
            learning_engine: The learning engine instance
            max_filename_length: Maximum filename length (without extension)
        """
        self.engine = learning_engine
        self.db = learning_engine.db
        self.max_length = max_filename_length
        
        # Default naming patterns by file type
        self.default_patterns = {
            ".pdf": "{date}_{case}_{type}",
            ".docx": "{date}_{case}_{type}",
            ".txt": "{date}_{description}",
            ".jpg": "{date}_{subject}_{seq}",
            ".png": "{date}_{subject}_{seq}",
            ".eml": "{date}_{sender}_{subject}",
            ".xlsx": "{date}_{report_type}",
        }
    
    def propose_rename(
        self,
        file_path: Path,
        content: Optional[str] = None,
        extracted_entities: Optional[Dict[str, Any]] = None
    ) -> RenameProposal:
        """
        Propose a new filename for a file.
        
        Args:
            file_path: Path to the file
            content: Optional file content
            extracted_entities: Optional pre-extracted entities
            
        Returns:
            RenameProposal with suggested name
        """
        original_name = file_path.name
        extension = file_path.suffix.lower()
        
        # Get components from various sources
        components = {}
        reasoning = []
        
        # From pre-extracted entities
        if extracted_entities:
            components.update(extracted_entities)
            reasoning.append("Using pre-extracted entities")
        
        # From filename analysis
        filename_components = self._analyze_filename(original_name)
        for key, value in filename_components.items():
            if key not in components:
                components[key] = value
        if filename_components:
            reasoning.append("Extracted components from original filename")
        
        # From content analysis
        if content:
            content_components = self._analyze_content(content)
            for key, value in content_components.items():
                if key not in components:
                    components[key] = value
            if content_components:
                reasoning.append("Extracted components from content")
        
        # Use LLM for complex analysis
        if self.engine.llm_enabled and content:
            llm_components = self._analyze_with_llm(file_path, content, components)
            if llm_components:
                components.update(llm_components)
                reasoning.append("Enhanced with LLM analysis")
        
        # Generate proposed name
        proposed_name = self._generate_filename(components, extension)
        
        # Calculate confidence
        confidence = self._calculate_confidence(components)
        
        return RenameProposal(
            original_path=file_path,
            proposed_name=proposed_name,
            proposed_path=file_path.parent / proposed_name,
            components=components,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def _analyze_filename(self, filename: str) -> Dict[str, str]:
        """Extract components from filename"""
        components = {}
        name_without_ext = Path(filename).stem
        
        # Try to extract date
        date_patterns = [
            (r'(\d{4})-(\d{2})-(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
            (r'(\d{2})-(\d{2})-(\d{4})', lambda m: f"{m.group(3)}-{m.group(1)}-{m.group(2)}"),
            (r'(\d{4})(\d{2})(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        ]
        
        for pattern, formatter in date_patterns:
            match = re.search(pattern, name_without_ext)
            if match:
                components["date"] = formatter(match)
                break
        
        # Try to extract case number
        case_patterns = [
            r'(\d{1,2})[:-]([A-Z]{2,3})[:-](\d{3,5})',
            r'([A-Z]{1,3})\s*(\d{2,4})[-\s](\d{4,6})',
        ]
        
        for pattern in case_patterns:
            match = re.search(pattern, name_without_ext)
            if match:
                components["case_number"] = match.group(0).replace(" ", "-")
                break
        
        return components
    
    def _analyze_content(self, content: str) -> Dict[str, str]:
        """Extract components from file content"""
        components = {}
        
        # Use learned patterns
        patterns = self.engine.get_active_patterns()
        
        for pattern in patterns:
            try:
                match = re.search(pattern.regex, content)
                if match:
                    # Use the first capturing group or full match
                    value = match.group(1) if match.groups() else match.group(0)
                    components[pattern.pattern_type] = value
            except re.error:
                continue
        
        return components
    
    def _analyze_with_llm(
        self,
        file_path: Path,
        content: str,
        existing_components: Dict[str, str]
    ) -> Dict[str, str]:
        """Use LLM to extract naming components"""
        model = self.engine._get_model()
        if not model:
            return {}
        
        prompt = f"""You are a file naming expert. Extract key metadata for creating a descriptive filename.

File: {file_path.name}
Already Extracted: {json.dumps(existing_components)}

Content (first 2000 chars):
---
{content[:2000]}
---

Extract these components if present (leave empty if not found):
- date: In YYYY-MM-DD format
- case_number: Legal case number
- document_type: Type of document (motion, order, brief, etc.)
- author: Who created the document
- subject: Main subject or title
- recipient: Who it's addressed to
- version: Version number if any

Respond with JSON only:
{{
    "date": "",
    "case_number": "",
    "document_type": "",
    "author": "",
    "subject": "",
    "recipient": "",
    "version": ""
}}
"""
        
        try:
            response = model.generate(prompt)
            data = json.loads(response)
            
            # Only return non-empty values
            return {k: v for k, v in data.items() if v}
            
        except Exception as e:
            logger.error(f"LLM naming analysis failed: {e}")
            return {}
    
    def _generate_filename(
        self,
        components: Dict[str, str],
        extension: str
    ) -> str:
        """Generate filename from components"""
        parts = []
        
        # Order of preference for naming components
        component_order = [
            "date",
            "case_number",
            "document_type",
            "subject",
            "author",
            "version"
        ]
        
        for comp in component_order:
            if comp in components and components[comp]:
                value = self._sanitize_component(components[comp])
                if value:
                    parts.append(value)
        
        if not parts:
            # Fallback to timestamp
            parts = [datetime.now().strftime("%Y-%m-%d_%H%M%S")]
        
        # Join with underscores
        name = "_".join(parts)
        
        # Truncate if too long
        if len(name) > self.max_length:
            name = name[:self.max_length]
        
        return name + extension
    
    def _sanitize_component(self, value: str) -> str:
        """Sanitize a component for use in filename"""
        if not value:
            return ""
        
        # Replace problematic characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', value)
        sanitized = re.sub(r'\s+', '_', sanitized)
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = sanitized.strip('_')
        
        # Title case if all lowercase
        if sanitized.islower():
            sanitized = sanitized.title()
        
        return sanitized
    
    def _calculate_confidence(self, components: Dict[str, str]) -> float:
        """Calculate confidence in the proposed name"""
        # More components = higher confidence
        key_components = ["date", "case_number", "document_type"]
        present = sum(1 for k in key_components if k in components and components[k])
        
        base_confidence = 0.3 + (present / len(key_components)) * 0.5
        
        # Bonus for date being properly formatted
        if "date" in components:
            if re.match(r'\d{4}-\d{2}-\d{2}', components["date"]):
                base_confidence += 0.1
        
        return min(1.0, base_confidence)
    
    def batch_propose(
        self,
        file_paths: List[Path],
        content_reader: Optional[callable] = None
    ) -> List[RenameProposal]:
        """
        Propose renames for multiple files.
        
        Args:
            file_paths: List of files to rename
            content_reader: Optional function to read file content
            
        Returns:
            List of RenameProposals
        """
        proposals = []
        
        for file_path in file_paths:
            content = None
            if content_reader:
                try:
                    content = content_reader(file_path)
                except Exception:
                    pass
            
            proposal = self.propose_rename(file_path, content)
            proposals.append(proposal)
        
        return proposals
    
    def apply_rename(
        self,
        proposal: RenameProposal,
        create_backup: bool = True,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Apply a rename proposal.
        
        Args:
            proposal: The rename proposal
            create_backup: Whether to create a backup first
            dry_run: If True, only report what would be done
            
        Returns:
            Result of the rename operation
        """
        result = {
            "success": False,
            "original": str(proposal.original_path),
            "new": str(proposal.proposed_path),
            "backup": None,
            "dry_run": dry_run,
            "error": None
        }
        
        if not proposal.original_path.exists():
            result["error"] = "Original file does not exist"
            return result
        
        if proposal.proposed_path.exists():
            result["error"] = "Target filename already exists"
            return result
        
        if dry_run:
            result["success"] = True
            result["new"] = str(proposal.proposed_path) + " (would rename)"
            return result
        
        try:
            # Create backup if requested
            if create_backup:
                backup_path = proposal.original_path.with_suffix(
                    proposal.original_path.suffix + ".backup"
                )
                shutil.copy2(proposal.original_path, backup_path)
                result["backup"] = str(backup_path)
            
            # Perform rename
            proposal.original_path.rename(proposal.proposed_path)
            
            result["success"] = True
            
            # Log the rename for learning
            self.engine.record_feedback(
                proposal.original_path,
                "rename",
                accepted=True,
                details={
                    "original": proposal.original_path.name,
                    "new": proposal.proposed_name,
                    "components": proposal.components
                }
            )
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def batch_apply(
        self,
        proposals: List[RenameProposal],
        min_confidence: float = 0.7,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Apply multiple rename proposals.
        
        Args:
            proposals: List of proposals to apply
            min_confidence: Only apply renames above this confidence
            dry_run: If True, only report what would be done
            
        Returns:
            Summary of all operations
        """
        results = {
            "total": len(proposals),
            "applied": [],
            "skipped": [],
            "errors": [],
            "dry_run": dry_run
        }
        
        for proposal in proposals:
            if proposal.confidence < min_confidence:
                results["skipped"].append({
                    "file": str(proposal.original_path),
                    "reason": f"Confidence {proposal.confidence:.0%} below threshold {min_confidence:.0%}"
                })
                continue
            
            result = self.apply_rename(proposal, dry_run=dry_run)
            
            if result["success"]:
                results["applied"].append(result)
            else:
                results["errors"].append(result)
        
        return results
    
    def learn_naming_pattern(
        self,
        file_type: str,
        examples: List[Tuple[str, Dict[str, str]]]
    ):
        """
        Learn a naming pattern from examples.
        
        Args:
            file_type: File extension (e.g., ".pdf")
            examples: List of (filename, components) tuples
        """
        if not self.engine.llm_enabled:
            return
        
        model = self.engine._get_model()
        if not model:
            return
        
        prompt = f"""Analyze these filename examples and infer the naming pattern.

File Type: {file_type}
Examples:
{json.dumps(examples[:10], indent=2)}

Identify:
1. The pattern structure (e.g., "{{date}}_{{case}}_{{type}}")
2. Required vs optional components
3. Separator characters used
4. Any consistent ordering

Respond with JSON:
{{
    "pattern": "{{component1}}_{{component2}}",
    "components": ["component1", "component2"],
    "required": ["component1"],
    "optional": ["component2"],
    "separator": "_"
}}
"""
        
        try:
            response = model.generate(prompt)
            data = json.loads(response)
            
            # Save learned pattern
            import uuid
            knowledge = FileNamingKnowledge(
                knowledge_id=str(uuid.uuid4()),
                file_type=file_type,
                naming_pattern=data.get("pattern", ""),
                components=data.get("components", []),
                examples=[e[0] for e in examples],
                success_rate=0.7
            )
            
            # Store in database
            with self.db.db_path.open('a') as f:
                pass  # TODO: Add proper storage
                
            logger.info(f"Learned naming pattern for {file_type}: {knowledge.naming_pattern}")
            
        except Exception as e:
            logger.error(f"Failed to learn naming pattern: {e}")
    
    def suggest_with_llm(
        self,
        file_path: Path,
        content: str
    ) -> Dict[str, Any]:
        """
        Get LLM suggestion for complete filename.
        
        Args:
            file_path: Current file path
            content: File content
            
        Returns:
            Complete suggestion with reasoning
        """
        if not self.engine.llm_enabled:
            return {"error": "LLM not enabled"}
        
        model = self.engine._get_model()
        if not model:
            return {"error": "Failed to get model"}
        
        prompt = f"""You are a file organization expert. Suggest the ideal filename for this document.

Current Filename: {file_path.name}
File Extension: {file_path.suffix}

Document Content (first 3000 chars):
---
{content[:3000]}
---

Requirements:
1. Use a clear, descriptive name
2. Include date (YYYY-MM-DD format) if available
3. Include key identifiers (case number, document type)
4. Use underscores, no spaces
5. Keep it under 80 characters (excluding extension)
6. Make it sortable (put date first if present)
7. Preserve the original extension

Respond with JSON:
{{
    "suggested_filename": "complete_filename_with_extension",
    "components_extracted": {{
        "date": "YYYY-MM-DD or null",
        "case_number": "value or null",
        "document_type": "value or null",
        "subject": "brief subject or null"
    }},
    "reasoning": "why this name is appropriate",
    "confidence": 0.0-1.0
}}
"""
        
        try:
            response = model.generate(prompt)
            data = json.loads(response)
            
            return {
                "success": True,
                "current": file_path.name,
                "suggested": data.get("suggested_filename", file_path.name),
                "components": data.get("components_extracted", {}),
                "reasoning": data.get("reasoning", ""),
                "confidence": data.get("confidence", 0.5)
            }
            
        except Exception as e:
            logger.error(f"LLM filename suggestion failed: {e}")
            return {"error": str(e)}
