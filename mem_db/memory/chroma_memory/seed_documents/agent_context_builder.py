#!/usr/bin/env python3
"""
AGENT CONTEXT BUILDER - Rich Context & Expert Prompts
====================================================

Builds comprehensive context packages for external LLMs to maximize their performance.
Each agent gets specialized knowledge, frameworks, and detailed instructions.
"""

import sqlite3  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict  # noqa: E402


class AgentContextBuilder:
    """Builds rich context packages for external agent deployment"""

    def __init__(self):
        self.db_path = "/workspace/app/databases/master_database.db"
        self.frameworks_path = (
            "/workspace/app/project_folder/Docker_experiment/Frameworks"
        )

    def build_alex_context(self) -> Dict[str, Any]:
        """Build comprehensive context for Alex _Code Analyst_"""

        # Get system inventory from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM file_system WHERE file_type = '.py'")
        python_files = cursor.fetchone()[0]

        cursor.execute(
            "SELECT file_path FROM file_system WHERE file_type = '.py' LIMIT 20"
        )
        sample_files = [row[0] for row in cursor.fetchall()]

        conn.close()

        context = {
            "role": "Senior Software Architect & Code Analysis Expert",
            "expertise": [
                "Large-scale Python codebase analysis",
                "Architectural pattern recognition",
                "Dependency mapping and system design",
                "Code quality assessment and optimization",
                "Enterprise software architecture",
            ],
            "current_system_overview": {
                "total_python_files": python_files,
                "sample_file_paths": sample_files,
                "key_systems": [
                    "data_mastery_system.py - Complete data ingestion",
                    "external_llm_coordinator.py - Multi-LLM coordination",
                    "token_tracker.py - Performance monitoring",
                    "system_bootstrap.py - System initialization",
                    "ai_boss_orchestrator.py - High-level orchestration",
                ],
            },
            "analysis_frameworks": [
                "SOLID Principles",
                "Clean Architecture patterns",
                "Dependency Injection analysis",
                "Design Pattern identification",
                "Performance bottleneck detection",
            ],
            "deliverable_requirements": {
                "format": "Structured JSON report",
                "categories": [
                    "Core Systems",
                    "Utilities",
                    "Agents",
                    "Data Management",
                    "Coordination",
                ],
                "analysis_depth": "Enterprise-grade with actionable insights",
                "focus_areas": [
                    "Reusability",
                    "Maintainability",
                    "Scalability",
                    "Performance",
                ],
            },
            "success_criteria": [
                "Clear categorization of all major components",
                "Identification of architectural strengths and weaknesses",
                "Specific recommendations for professional reorganization",
                "Dependency mapping for safe refactoring",
            ],
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
                "Scalable system design",
            ],
            "frameworks_available": frameworks,
            "mece_principles": {
                "mutually_exclusive": "Each category must be distinct with no overlap",
                "collectively_exhaustive": "Categories must cover entire problem space",
                "benefits": [
                    "Prevents redundancy and analysis overlap",
                    "Ensures comprehensive coverage",
                    "Improves communication clarity",
                    "Enhances problem-solving efficiency",
                ],
            },
            "current_system_state": {
                "total_directories": "20+ major directories",
                "organizational_challenges": [
                    "Mixed concerns in single directories",
                    "Duplicate functionality across files",
                    "Unclear separation of responsibilities",
                    "Inconsistent naming conventions",
                ],
            },
            "target_domains": [
                "Data Management Systems",
                "Task Automation Frameworks",
                "Agent Coordination Infrastructure",
                "Knowledge Management Systems",
                "Performance Optimization Tools",
            ],
            "deliverable_requirements": {
                "format": "Detailed architectural blueprint",
                "must_include": [
                    "Complete MECE-compliant folder structure",
                    "Clear responsibility boundaries",
                    "Migration strategy with dependencies",
                    "Professional naming conventions",
                    "Integration patterns between domains",
                ],
            },
            "success_criteria": [
                "Zero functional overlap between domains",
                "100% coverage of existing functionality",
                "Enterprise-grade professional organization",
                "Clear scalability path for future growth",
            ],
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
                "Enterprise deployment practices",
            ],
            "implementation_requirements": {
                "safety_first": "Preserve all existing functionality",
                "testing_strategy": "Validate each migration step",
                "rollback_capability": "Maintain ability to revert changes",
                "documentation": "Document all changes and decisions",
            },
            "available_tools": [
                "Python file operations",
                "SQLite database management",
                "Git version control",
                "Automated testing frameworks",
                "System monitoring tools",
            ],
            "migration_strategy": {
                "phases": [
                    "Backup existing systems",
                    "Create new directory structure",
                    "Migrate files with dependency order",
                    "Update import paths and references",
                    "Validate functionality preservation",
                    "Clean up deprecated structures",
                ]
            },
            "deliverable_requirements": {
                "format": "Fully functional reorganized system",
                "must_preserve": [
                    "All existing functionality",
                    "Database integrity",
                    "Configuration settings",
                    "API interfaces",
                    "Performance characteristics",
                ],
            },
            "success_criteria": [
                "Zero functionality regression",
                "Professional directory structure",
                "All tests passing",
                "Improved maintainability",
                "Clear documentation of changes",
            ],
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
            "SWOT Analysis Framework .txt",
        ]

        for filename in framework_files:
            try:
                filepath = Path(self.frameworks_path) / filename
                if filepath.exists():
                    with open(filepath, "r", encoding="utf-8") as f:
                        frameworks[filename.replace(".txt", "")] = f.read()
            except Exception as e:
                print(f"Could not load framework {filename}: {e}")

        return frameworks

    def generate_expert_prompt(
        self, agent_name: str, task_type: str, task_data: str
    ) -> str:
        """Generate expert-level prompt with rich context"""

        context_builders = {
            "Alex _Code Analyst_": self.build_alex_context,
            "Riley _Refactoring Planner_": self.build_riley_context,
            "Jordan _Implementation Specialist_": self.build_jordan_context,
        }

        if agent_name not in context_builders:
            return task_data

        context = context_builders[agent_name]()  # noqa: F841

        expert_prompt = """
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


if __name__ == "__main__":
    builder = AgentContextBuilder()

    # Example: Build context for Alex
    alex_prompt = builder.generate_expert_prompt(
        "Alex _Code Analyst_",
        "comprehensive_code_analysis",
        "Analyze the complete codebase for professional reorganization",
    )

    print("SAMPLE EXPERT PROMPT FOR ALEX:")
    print("=" * 50)
    print(alex_prompt[:1000] + "...")
