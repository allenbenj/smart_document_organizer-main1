#!/usr/bin/env python3
"""
AGENT CONTEXT BUILDER - Rich Context & Expert Prompts
====================================================

Builds comprehensive context packages for external LLMs to maximize their performance.
Each agent gets specialized knowledge, frameworks, and detailed instructions.
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional

class AgentContextBuilder:
    """Builds rich context packages for external agent deployment"""
    
    def __init__(self):
        self.db_path = "/workspace/app/databases/master_database.db"
        self.frameworks_path = "/workspace/app/project_folder/Docker_experiment/Frameworks"
        
    def build_alex_context(self) -> Dict[str, Any]:
        """Build comprehensive context for Alex _Code Analyst_"""
        
        # Get system inventory from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM file_system WHERE file_type = '.py'")
        python_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT file_path FROM file_system WHERE file_type = '.py' LIMIT 20")
        sample_files = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        context = {
            "role": "Senior Software Architect & Code Analysis Expert",
            "expertise": [
                "Large-scale Python codebase analysis",
                "Architectural pattern recognition", 
                "Dependency mapping and system design",
                "Code quality assessment and optimization",
                "Enterprise software architecture"
            ],
            "current_system_overview": {
                "total_python_files": python_files,
                "sample_file_paths": sample_files,
                "key_systems": [
                    "data_mastery_system.py - Complete data ingestion",
                    "external_llm_coordinator.py - Multi-LLM coordination", 
                    "token_tracker.py - Performance monitoring",
                    "system_bootstrap.py - System initialization",
                    "ai_boss_orchestrator.py - High-level orchestration"
                ]
            },
            "analysis_frameworks": [
                "SOLID Principles",
                "Clean Architecture patterns",
                "Dependency Injection analysis", 
                "Design Pattern identification",
                "Performance bottleneck detection"
            ],
            "deliverable_requirements": {
                "format": "Structured JSON report",
                "categories": ["Core Systems", "Utilities", "Agents", "Data Management", "Coordination"],
                "analysis_depth": "Enterprise-grade with actionable insights",
                "focus_areas": ["Reusability", "Maintainability", "Scalability", "Performance"]
            },
            "success_criteria": [
                "Clear categorization of all major components",
                "Identification of architectural strengths and weaknesses",
                "Specific recommendations for professional reorganization",
                "Dependency mapping for safe refactoring"
            ]
        }
        
        return context
    
    def build_riley_context(self) -> Dict[str, Any]:
        """Build comprehensive context for Riley _Refactoring Planner_"""
        
        # Load MECE and other frameworks
        frameworks = self._load_reasoning_frameworks()
        
        context = {
            "role": "Enterprise Architecture Strategist & MECE Framework Expert",
            "expertise": [
                "MECE Principle application",
                "Enterprise software architecture design",
                "Strategic refactoring and system reorganization",
                "Best practices implementation",
                "Scalable system design"
            ],
            "frameworks_available": frameworks,
            "mece_principles": {
                "mutually_exclusive": "Each category must be distinct with no overlap",
                "collectively_exhaustive": "Categories must cover entire problem space",
                "benefits": [
                    "Prevents redundancy and analysis overlap",
                    "Ensures comprehensive coverage",
                    "Improves communication clarity", 
                    "Enhances problem-solving efficiency"
                ]
            },
            "current_system_state": {
                "total_directories": "20+ major directories",
                "organizational_challenges": [
                    "Mixed concerns in single directories",
                    "Duplicate functionality across files",
                    "Unclear separation of responsibilities",
                    "Inconsistent naming conventions"
                ]
            },
            "target_domains": [
                "Data Management Systems",
                "Task Automation Frameworks",
                "Agent Coordination Infrastructure", 
                "Knowledge Management Systems",
                "Performance Optimization Tools"
            ],
            "deliverable_requirements": {
                "format": "Detailed architectural blueprint",
                "must_include": [
                    "Complete MECE-compliant folder structure",
                    "Clear responsibility boundaries",
                    "Migration strategy with dependencies",
                    "Professional naming conventions",
                    "Integration patterns between domains"
                ]
            },
            "success_criteria": [
                "Zero functional overlap between domains",
                "100% coverage of existing functionality", 
                "Enterprise-grade professional organization",
                "Clear scalability path for future growth"
            ]
        }
        
        return context
    
    def build_jordan_context(self) -> Dict[str, Any]:
        """Build comprehensive context for Jordan _Implementation Specialist_"""
        
        context = {
            "role": "Senior DevOps Engineer & System Implementation Expert",
            "expertise": [
                "Large-scale file system reorganization",
                "Safe refactoring and migration strategies",
                "Automated deployment and configuration",
                "System integration and testing",
                "Enterprise deployment practices"
            ],
            "implementation_requirements": {
                "safety_first": "Preserve all existing functionality",
                "testing_strategy": "Validate each migration step",
                "rollback_capability": "Maintain ability to revert changes",
                "documentation": "Document all changes and decisions"
            },
            "available_tools": [
                "Python file operations",
                "SQLite database management", 
                "Git version control",
                "Automated testing frameworks",
                "System monitoring tools"
            ],
            "migration_strategy": {
                "phases": [
                    "Backup existing systems",
                    "Create new directory structure", 
                    "Migrate files with dependency order",
                    "Update import paths and references",
                    "Validate functionality preservation",
                    "Clean up deprecated structures"
                ]
            },
            "deliverable_requirements": {
                "format": "Fully functional reorganized system",
                "must_preserve": [
                    "All existing functionality",
                    "Database integrity",
                    "Configuration settings", 
                    "API interfaces",
                    "Performance characteristics"
                ]
            },
            "success_criteria": [
                "Zero functionality regression",
                "Professional directory structure",
                "All tests passing",
                "Improved maintainability",
                "Clear documentation of changes"
            ]
        }
        
        return context
    
    def _load_reasoning_frameworks(self) -> Dict[str, str]:
        """Load reasoning frameworks from Agent Zero documentation"""
        frameworks = {}
        
        framework_files = [
            "MECE Principle .txt",
            "Critical Thinking Framework.txt", 
            "IRAC.txt",
            "Issue Trees.txt",
            "SWOT Analysis Framework .txt"
        ]
        
        for filename in framework_files:
            try:
                filepath = Path(self.frameworks_path) / filename
                if filepath.exists():
                    with open(filepath, 'r', encoding='utf-8') as f:
                        frameworks[filename.replace('.txt', '')] = f.read()
            except Exception as e:
                print(f"Could not load framework {filename}: {e}")
        
        return frameworks


# ---- Capability Degradation Utilities ----

def build_degradation_notice(
    component: str,
    lost_features: List[str],
    reason: str,
    suggested_actions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a standard degradation notice describing what the user loses.

    Include this in API responses/metadata so users understand impacts and can
    decide whether it fits their workflow.
    """
    return {
        "component": component,
        "lost_features": lost_features,
        "reason": reason,
        "fits_workflow": False,
        "suggested_actions": suggested_actions or [],
    }

    
    def generate_expert_prompt(self, agent_name: str, task_type: str, task_data: str) -> str:
        """Generate expert-level prompt with rich context"""
        
        context_builders = {
            # Engineering personas
            "Alex _Code Analyst_": self.build_alex_context,
            "Riley _Refactoring Planner_": self.build_riley_context,
            "Jordan _Implementation Specialist_": self.build_jordan_context,
            # Legal personas
            "Lex _Legal Researcher_": self.build_legal_researcher_context,
            "Ava _Legal Writer_": self.build_legal_writer_context,
            "Max _Detail Analyst_": self.build_detail_analyst_context,
            "Aria _Appellate Specialist_": self.build_appellate_specialist_context,
        }
        
        if agent_name not in context_builders:
            return task_data
        
        context = context_builders[agent_name]()
        
        expert_prompt = f"""
# {context['role']}

## Your Expertise
{chr(10).join('- ' + exp for exp in context['expertise'])}

## Current Context
{json.dumps(context.get('current_system_overview', context.get('current_system_state', {})), indent=2)}

## Task: {task_type}
{task_data}

## Frameworks & Tools Available
{json.dumps(context.get('frameworks_available', context.get('available_tools', [])), indent=2)}

## Deliverable Requirements
{json.dumps(context['deliverable_requirements'], indent=2)}

## Success Criteria
{chr(10).join('✅ ' + criteria for criteria in context['success_criteria'])}

## Instructions
You are an expert {context['role']}. Use your specialized knowledge and the provided context to deliver enterprise-grade results. Be thorough, professional, and focus on practical implementation. Your output will be used by other experts, so maintain high technical standards.

Respond with detailed, actionable recommendations that demonstrate your expertise in this domain.
"""
        
        return expert_prompt

    # -------- Legal expert contexts --------
    def _ontology_overview(self) -> Dict[str, Any]:
        try:
            from agents.entities.ontology.ontology import get_entity_types_for_prompt, get_relationship_types_for_prompt
            return {
                "entity_types": get_entity_types_for_prompt(),
                "relationship_types": get_relationship_types_for_prompt(),
            }
        except Exception:
            return {"entity_types": "N/A", "relationship_types": "N/A"}

    def _knowledge_stats(self) -> Dict[str, Any]:
        try:
            from mem_db.knowledge import get_knowledge_manager
            mgr = get_knowledge_manager()
            ents = len(getattr(mgr, "_entities", {})) if mgr else 0
            rels = len(getattr(mgr, "_relationships", {})) if mgr else 0
            return {"entities": ents, "relationships": rels}
        except Exception:
            return {"entities": 0, "relationships": 0}

    def build_legal_researcher_context(self) -> Dict[str, Any]:
        ontology = self._ontology_overview()
        kstats = self._knowledge_stats()
        return {
            "role": "Expert Legal Researcher & Analyst",
            "expertise": [
                "Primary and secondary legal research",
                "Case law synthesis and precedent mapping",
                "Statutory interpretation and regulatory analysis",
                "Citations (Bluebook) and authority hierarchy",
                "Issue spotting and IRAC/Toulmin frameworks",
            ],
            "current_system_overview": {
                "knowledge_graph": kstats,
                "ontology": ontology,
            },
            "frameworks_available": ["IRAC", "Toulmin", "Critical Thinking", "MECE"],
            "deliverable_requirements": {
                "format": "Structured memo with citations",
                "sections": ["Issues", "Rules", "Application", "Conclusion", "Key Citations"],
                "citation_style": "Bluebook",
                "quality": "Comprehensive and precise",
            },
            "success_criteria": [
                "Accurate identification of controlling authority",
                "Clear articulation of rules and exceptions",
                "Thorough application with counterarguments",
                "Actionable and concise conclusions",
            ],
        }

    def build_legal_writer_context(self) -> Dict[str, Any]:
        ontology = self._ontology_overview()
        return {
            "role": "Professional Legal Writer & Editor",
            "expertise": [
                "Persuasive brief writing",
                "Clarity, structure, and style",
                "Plain language without loss of precision",
                "Audience-aware drafting (court/client/partner)",
                "Quality control and consistency",
            ],
            "current_system_overview": {"ontology": ontology},
            "frameworks_available": ["CREAC", "IRAC", "Issue Trees"],
            "deliverable_requirements": {
                "format": "Polished legal text",
                "tone": "Professional and authoritative",
                "must_include": ["Clear headings", "Logical flow", "Defined asks"],
            },
            "success_criteria": [
                "Clear, concise, and persuasive",
                "Accurate legal terminology and citations",
                "Consistent voice and strong transitions",
            ],
        }

    def build_detail_analyst_context(self) -> Dict[str, Any]:
        return {
            "role": "Detail-Oriented Legal Analyst",
            "expertise": [
                "Error and contradiction detection",
                "Compliance gap analysis",
                "Assumption and ambiguity identification",
                "Risk and mitigation mapping",
            ],
            "available_tools": ["Contradiction detector", "Violation review", "Entity extraction"],
            "deliverable_requirements": {
                "format": "Findings report",
                "must_include": ["Issue", "Evidence", "Impact", "Recommendation"],
            },
            "success_criteria": [
                "High recall of issues with low noise",
                "Evidence-backed findings",
                "Concrete next steps",
            ],
        }

    def build_appellate_specialist_context(self) -> Dict[str, Any]:
        return {
            "role": "Appellate Specialist",
            "expertise": [
                "Standards of review (de novo, abuse of discretion, substantial evidence)",
                "Issue preservation and error review",
                "Record on appeal and procedural compliance",
                "Precedent synthesis and persuasive authority",
                "Appellate brief drafting and oral argument strategy",
            ],
            "frameworks_available": ["CREAC", "IRAC", "Precedent Mapping", "Issue Trees"],
            "deliverable_requirements": {
                "format": "Appellate analysis or brief section",
                "sections": ["Questions Presented", "Standard of Review", "Argument", "Conclusion"],
                "citation_style": "Bluebook",
            },
            "success_criteria": [
                "Correct standard of review selection and application",
                "Strong use of binding authority and persuasive citations",
                "Logical structure and clear asks",
            ],
        }

if __name__ == "__main__":
    builder = AgentContextBuilder()
    
    # Example: Build context for Alex
    alex_prompt = builder.generate_expert_prompt(
        "Alex _Code Analyst_",
        "comprehensive_code_analysis", 
        "Analyze the complete codebase for professional reorganization"
    )
    
    print("SAMPLE EXPERT PROMPT FOR ALEX:")
    print("=" * 50)
    print(alex_prompt[:1000] + "...")
