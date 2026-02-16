"""
Structure Optimizer - Creates and Refines Folder Structures

This module optimizes folder organization by:
- Analyzing existing structures and finding improvements
- Creating new folders based on document patterns
- Reorganizing files for better navigation
- Learning from user preferences
"""

import os
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from collections import defaultdict

from .learning_engine import LearningEngine, LearnedFolderStructure

logger = logging.getLogger(__name__)


@dataclass
class FolderSuggestion:
    """A suggested folder structure change"""
    action: str  # create, rename, merge, move
    path: Path
    new_path: Optional[Path] = None
    reason: str = ""
    confidence: float = 0.5
    files_affected: int = 0


@dataclass
class StructureAnalysis:
    """Analysis of current folder structure"""
    total_folders: int
    total_files: int
    max_depth: int
    empty_folders: List[Path]
    overcrowded_folders: List[tuple[Path, int]]  # path, file count
    inconsistent_naming: List[Path]
    suggested_improvements: List[FolderSuggestion]


class StructureOptimizer:
    """
    Optimizes folder structures for better organization.
    
    Uses LLM to:
    - Analyze folder hierarchies and suggest improvements
    - Create logical subfolder structures
    - Identify and fix organizational issues
    - Learn optimal structures from user behavior
    """
    
    def __init__(
        self,
        learning_engine: LearningEngine,
        max_files_per_folder: int = 50,
        max_depth: int = 5
    ):
        """
        Initialize the structure optimizer.
        
        Args:
            learning_engine: The learning engine instance
            max_files_per_folder: Threshold for folder crowding
            max_depth: Maximum recommended folder depth
        """
        self.engine = learning_engine
        self.db = learning_engine.db
        self.max_files = max_files_per_folder
        self.max_depth = max_depth
        
        # Standard legal folder templates
        self.templates = {
            "legal_case": [
                "01_Court_Record",
                "01_Court_Record/Pleadings",
                "01_Court_Record/Motions",
                "01_Court_Record/Orders",
                "02_Discovery",
                "02_Discovery/Requests",
                "02_Discovery/Responses",
                "02_Discovery/Depositions",
                "03_Evidence",
                "03_Evidence/Documents",
                "03_Evidence/Photos",
                "04_Research",
                "04_Research/Case_Law",
                "04_Research/Statutes",
                "05_Analysis",
                "05_Analysis/Memos",
                "05_Analysis/Timelines",
                "06_Correspondence",
                "07_Working",
                "08_Media",
                "10_Archive"
            ],
            "general": [
                "Documents",
                "Images",
                "Media",
                "Archive"
            ]
        }
    
    def analyze_structure(self, root_path: Path) -> StructureAnalysis:
        """
        Analyze the current folder structure.
        
        Args:
            root_path: Root path to analyze
            
        Returns:
            StructureAnalysis with findings
        """
        if not root_path.exists():
            raise ValueError(f"Path does not exist: {root_path}")
        
        total_folders = 0
        total_files = 0
        max_depth = 0
        empty_folders = []
        overcrowded_folders = []
        inconsistent_naming = []
        
        # Walk the structure
        for dirpath, dirnames, filenames in os.walk(root_path):
            current_path = Path(dirpath)
            depth = len(current_path.relative_to(root_path).parts)
            max_depth = max(max_depth, depth)
            total_folders += 1
            total_files += len(filenames)
            
            # Check for empty folders
            if not filenames and not dirnames:
                empty_folders.append(current_path)
            
            # Check for overcrowded folders
            if len(filenames) > self.max_files:
                overcrowded_folders.append((current_path, len(filenames)))
            
            # Check naming consistency
            if not self._is_consistent_naming(current_path.name):
                inconsistent_naming.append(current_path)
        
        # Generate improvement suggestions
        suggestions = self._generate_suggestions(
            root_path, empty_folders, overcrowded_folders, 
            inconsistent_naming, max_depth
        )
        
        return StructureAnalysis(
            total_folders=total_folders,
            total_files=total_files,
            max_depth=max_depth,
            empty_folders=empty_folders,
            overcrowded_folders=overcrowded_folders,
            inconsistent_naming=inconsistent_naming,
            suggested_improvements=suggestions
        )
    
    def _is_consistent_naming(self, name: str) -> bool:
        """Check if folder name follows consistent conventions"""
        # Skip root-like names
        if len(name) <= 2:
            return True
        
        # Good patterns: numbered prefix, underscore/hyphen separation, CamelCase
        import re
        good_patterns = [
            r'^\d{2}_\w+',  # 01_FolderName
            r'^[A-Z][a-z]+(?:[A-Z][a-z]+)*$',  # CamelCase
            r'^[a-z]+(?:_[a-z]+)*$',  # snake_case
            r'^[a-z]+(?:-[a-z]+)*$',  # kebab-case
        ]
        
        return any(re.match(p, name) for p in good_patterns)
    
    def _generate_suggestions(
        self,
        root_path: Path,
        empty_folders: List[Path],
        overcrowded: List[tuple[Path, int]],
        inconsistent: List[Path],
        max_depth: int
    ) -> List[FolderSuggestion]:
        """Generate improvement suggestions"""
        suggestions = []
        
        # Suggest removing empty folders
        for folder in empty_folders:
            suggestions.append(FolderSuggestion(
                action="remove",
                path=folder,
                reason="Empty folder with no files",
                confidence=0.8
            ))
        
        # Suggest splitting overcrowded folders
        for folder, count in overcrowded:
            suggestions.append(FolderSuggestion(
                action="split",
                path=folder,
                reason=f"Folder has {count} files, exceeding limit of {self.max_files}",
                confidence=0.9,
                files_affected=count
            ))
        
        # Suggest renaming inconsistent folders
        for folder in inconsistent:
            new_name = self._suggest_folder_name(folder.name)
            if new_name != folder.name:
                suggestions.append(FolderSuggestion(
                    action="rename",
                    path=folder,
                    new_path=folder.parent / new_name,
                    reason=f"Inconsistent naming: '{folder.name}' → '{new_name}'",
                    confidence=0.7
                ))
        
        return suggestions
    
    def _suggest_folder_name(self, current_name: str) -> str:
        """Suggest a better folder name"""
        import re
        
        # Clean up common issues
        name = current_name
        
        # Remove multiple spaces/underscores
        name = re.sub(r'[\s_]+', '_', name)
        
        # Add numbered prefix if missing
        if not re.match(r'^\d{2}_', name):
            # Don't add prefix to generic names
            generic = ['documents', 'files', 'misc', 'other', 'temp']
            if name.lower() not in generic:
                name = f"00_{name}"
        
        # Convert to Title_Case
        parts = name.split('_')
        if parts[0].isdigit():
            parts = [parts[0]] + [p.capitalize() for p in parts[1:]]
        else:
            parts = [p.capitalize() for p in parts]
        
        return '_'.join(parts)
    
    def create_structure(
        self,
        root_path: Path,
        template: str = "legal_case",
        document_types: Optional[List[str]] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Create an optimized folder structure.
        
        Args:
            root_path: Where to create the structure
            template: Template to use (legal_case, general)
            document_types: Additional folders for document types
            dry_run: If True, only report what would be created
            
        Returns:
            Report of created/planned folders
        """
        folders_to_create = list(self.templates.get(template, self.templates["general"]))
        
        # Add document-type specific folders
        if document_types:
            for doc_type in document_types:
                folder_name = self._document_type_to_folder(doc_type)
                if folder_name and folder_name not in folders_to_create:
                    folders_to_create.append(folder_name)
        
        result = {
            "root": str(root_path),
            "template": template,
            "folders_planned": folders_to_create,
            "folders_created": [],
            "folders_existing": [],
            "dry_run": dry_run
        }
        
        for folder in folders_to_create:
            folder_path = root_path / folder
            
            if folder_path.exists():
                result["folders_existing"].append(str(folder_path))
            elif not dry_run:
                folder_path.mkdir(parents=True, exist_ok=True)
                result["folders_created"].append(str(folder_path))
                logger.info(f"Created folder: {folder_path}")
            else:
                result["folders_created"].append(str(folder_path) + " (would create)")
        
        return result
    
    def _document_type_to_folder(self, doc_type: str) -> Optional[str]:
        """Convert document type to folder path"""
        type_mapping = {
            "motion": "01_Court_Record/Motions",
            "order": "01_Court_Record/Orders",
            "pleading": "01_Court_Record/Pleadings",
            "brief": "04_Research/Briefs",
            "memo": "05_Analysis/Memos",
            "deposition": "02_Discovery/Depositions",
            "exhibit": "03_Evidence/Exhibits",
            "correspondence": "06_Correspondence",
            "email": "06_Correspondence/Emails",
            "contract": "Legal_Documents/Contracts",
            "invoice": "Financial/Invoices",
        }
        return type_mapping.get(doc_type.lower())
    
    def optimize_with_llm(
        self,
        root_path: Path,
        file_samples: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to suggest optimal structure based on files.
        
        Args:
            root_path: Root path to optimize
            file_samples: Sample files with their metadata
            
        Returns:
            LLM-suggested optimization plan
        """
        if not self.engine.llm_enabled:
            return {"error": "LLM not enabled"}
        
        model = self.engine._get_model()
        if not model:
            return {"error": "Failed to get LLM model"}
        
        # Get current structure
        current_structure = []
        for dirpath, dirnames, filenames in os.walk(root_path):
            rel_path = Path(dirpath).relative_to(root_path)
            if str(rel_path) != ".":
                current_structure.append(str(rel_path))
            for f in filenames[:5]:  # Sample files
                current_structure.append(f"  📄 {f}")
        
        prompt = f"""You are a file organization expert. Analyze this folder structure and suggest improvements.

Current Structure:
{chr(10).join(current_structure[:50])}

{f"Sample Files with Metadata: {json.dumps(file_samples[:10], indent=2)}" if file_samples else ""}

Goals:
1. Create a logical, navigable hierarchy
2. Group related documents together
3. Use numbered prefixes for ordering (01_, 02_, etc.)
4. Optimize for both humans and automated processing
5. Consider document lifecycle (working → filed → archived)

Respond with JSON:
{{
    "analysis": "brief analysis of current structure",
    "issues": ["issue1", "issue2"],
    "recommended_structure": [
        "01_FolderA",
        "01_FolderA/SubfolderA1",
        "02_FolderB"
    ],
    "file_movements": [
        {{"from": "old/path", "to": "new/path", "reason": "why"}}
    ],
    "folder_renames": [
        {{"from": "old_name", "to": "new_name", "reason": "why"}}
    ],
    "reasoning": ["reason1", "reason2"]
}}
"""
        
        try:
            response = model.generate(prompt)
            data = json.loads(response)
            
            return {
                "success": True,
                "analysis": data.get("analysis", ""),
                "issues": data.get("issues", []),
                "recommended_structure": data.get("recommended_structure", []),
                "file_movements": data.get("file_movements", []),
                "folder_renames": data.get("folder_renames", []),
                "reasoning": data.get("reasoning", [])
            }
            
        except Exception as e:
            logger.error(f"LLM optimization failed: {e}")
            return {"error": str(e)}
    
    def apply_optimization(
        self,
        root_path: Path,
        optimization_plan: Dict[str, Any],
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Apply an optimization plan.
        
        Args:
            root_path: Root path
            optimization_plan: Plan from optimize_with_llm
            dry_run: If True, only report what would be done
            
        Returns:
            Results of applying the plan
        """
        results = {
            "folders_created": [],
            "folders_renamed": [],
            "files_moved": [],
            "errors": [],
            "dry_run": dry_run
        }
        
        # Create recommended structure
        for folder in optimization_plan.get("recommended_structure", []):
            folder_path = root_path / folder
            if not folder_path.exists():
                if dry_run:
                    results["folders_created"].append(f"{folder_path} (would create)")
                else:
                    try:
                        folder_path.mkdir(parents=True, exist_ok=True)
                        results["folders_created"].append(str(folder_path))
                    except Exception as e:
                        results["errors"].append(f"Failed to create {folder_path}: {e}")
        
        # Rename folders
        for rename in optimization_plan.get("folder_renames", []):
            old_path = root_path / rename["from"]
            new_path = root_path / rename["to"]
            
            if old_path.exists() and not new_path.exists():
                if dry_run:
                    results["folders_renamed"].append(f"{old_path} → {new_path} (would rename)")
                else:
                    try:
                        old_path.rename(new_path)
                        results["folders_renamed"].append(f"{old_path} → {new_path}")
                    except Exception as e:
                        results["errors"].append(f"Failed to rename {old_path}: {e}")
        
        # Move files
        for movement in optimization_plan.get("file_movements", []):
            old_path = root_path / movement["from"]
            new_path = root_path / movement["to"]
            
            if old_path.exists():
                if dry_run:
                    results["files_moved"].append(f"{old_path} → {new_path} (would move)")
                else:
                    try:
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(old_path), str(new_path))
                        results["files_moved"].append(f"{old_path} → {new_path}")
                    except Exception as e:
                        results["errors"].append(f"Failed to move {old_path}: {e}")
        
        return results
    
    def learn_from_user_organization(
        self,
        root_path: Path,
        document_type: str
    ):
        """
        Learn from how the user organized files.
        
        This records the current structure for a document type so it can
        be replicated for similar documents in the future.
        """
        # Find where files of this type are stored
        file_locations = []
        
        for dirpath, _, filenames in os.walk(root_path):
            for filename in filenames:
                # Simple check - in production, would use file analysis
                if document_type.lower() in filename.lower() or document_type.lower() in dirpath.lower():
                    rel_path = Path(dirpath).relative_to(root_path)
                    file_locations.append(str(rel_path))
        
        if not file_locations:
            return
        
        # Find most common location
        from collections import Counter
        most_common = Counter(file_locations).most_common(1)
        if not most_common:
            return
        
        recommended_path = most_common[0][0]
        
        # Save learned structure
        import uuid
        structure = LearnedFolderStructure(
            structure_id=str(uuid.uuid4()),
            document_type=document_type,
            recommended_path=recommended_path,
            naming_convention="",
            examples=file_locations[:10],
            usage_count=len(file_locations),
            satisfaction_score=0.7  # Start moderate
        )
        
        self.db.save_folder_structure(structure)
        logger.info(f"Learned structure for {document_type}: {recommended_path}")
