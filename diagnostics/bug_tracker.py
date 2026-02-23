"""
Bug Tracker - Capture and persist bugs/issues for user reporting

Provides in-app bug tracking so users can document failures without losing context.
Bugs saved to: logs/bugs.json
"""

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class Bug:
    """Represents a tracked bug/issue."""
    
    def __init__(
        self,
        title: str,
        description: str,
        category: str = "General",
        severity: str = "Medium",
        component: Optional[str] = None,
        error_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
        reproduction_steps: Optional[List[str]] = None,
        environment: Optional[Dict[str, Any]] = None
    ):
        self.id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        self.title = title
        self.description = description
        self.category = category  # "Startup", "API", "UI", "Processing", "General"
        self.severity = severity  # "Critical", "High", "Medium", "Low"
        self.component = component  # Tab name, module name, etc.
        self.error_message = error_message
        self.stack_trace = stack_trace
        self.reproduction_steps = reproduction_steps or []
        self.environment = environment or {}
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.status = "Open"  # "Open", "In Progress", "Fixed", "Won't Fix"
        self.notes = []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert bug to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "severity": self.severity,
            "component": self.component,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "reproduction_steps": self.reproduction_steps,
            "environment": self.environment,
            "created_at": self.created_at,
            "status": self.status,
            "notes": self.notes
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Bug':
        """Create bug from dictionary."""
        bug = cls(
            title=data['title'],
            description=data['description'],
            category=data.get('category', 'General'),
            severity=data.get('severity', 'Medium'),
            component=data.get('component'),
            error_message=data.get('error_message'),
            stack_trace=data.get('stack_trace'),
            reproduction_steps=data.get('reproduction_steps'),
            environment=data.get('environment')
        )
        bug.id = data['id']
        bug.created_at = data['created_at']
        bug.status = data.get('status', 'Open')
        bug.notes = data.get('notes', [])
        return bug


class BugTracker:
    """Track bugs and issues in the application."""
    
    def __init__(self, storage_file: str = "logs/bugs.json"):
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(exist_ok=True)
        self.bugs: List[Bug] = []
        self.load()
        
    def load(self):
        """Load bugs from storage."""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.bugs = [Bug.from_dict(bug_data) for bug_data in data]
                print(f"[BugTracker] Loaded {len(self.bugs)} existing bugs")
            except Exception as e:
                print(f"[BugTracker] Warning: Could not load bugs: {e}")
                self.bugs = []
        else:
            self.bugs = []
            
    def save(self):
        """Save bugs to storage."""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump([bug.to_dict() for bug in self.bugs], f, indent=2)
        except Exception as e:
            print(f"[BugTracker] Error saving bugs: {e}")
            
    def add_bug(
        self,
        title: str,
        description: str,
        **kwargs
    ) -> Bug:
        """Add a new bug."""
        bug = Bug(title=title, description=description, **kwargs)
        self.bugs.append(bug)
        self.save()
        print(f"[BugTracker] Added bug: {bug.id} - {title}")
        return bug
        
    def capture_exception(
        self,
        title: str,
        exc: Exception,
        component: Optional[str] = None,
        **kwargs
    ) -> Bug:
        """Capture an exception as a bug."""
        bug = self.add_bug(
            title=title,
            description=f"Exception occurred in {component or 'application'}",
            component=component,
            error_message=str(exc),
            stack_trace=traceback.format_exc(),
            severity="High",
            category="Error",
            **kwargs
        )
        return bug
        
    def get_bugs(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        component: Optional[str] = None
    ) -> List[Bug]:
        """Get bugs with optional filtering."""
        filtered = self.bugs
        
        if category:
            filtered = [b for b in filtered if b.category == category]
        if severity:
            filtered = [b for b in filtered if b.severity == severity]
        if status:
            filtered = [b for b in filtered if b.status == status]
        if component:
            filtered = [b for b in filtered if b.component == component]
            
        return filtered
        
    def update_bug_status(self, bug_id: str, status: str, note: Optional[str] = None):
        """Update bug status."""
        for bug in self.bugs:
            if bug.id == bug_id:
                bug.status = status
                if note:
                    bug.notes.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "note": note
                    })
                self.save()
                return True
        return False
        
    def get_summary(self) -> Dict[str, Any]:
        """Get bug summary statistics."""
        total = len(self.bugs)
        by_severity = {}
        by_category = {}
        by_status = {}
        
        for bug in self.bugs:
            by_severity[bug.severity] = by_severity.get(bug.severity, 0) + 1
            by_category[bug.category] = by_category.get(bug.category, 0) + 1
            by_status[bug.status] = by_status.get(bug.status, 0) + 1
            
        return {
            "total": total,
            "by_severity": by_severity,
            "by_category": by_category,
            "by_status": by_status,
            "storage_file": str(self.storage_file)
        }
        
    def export_report(self, output_file: Optional[str] = None) -> str:
        """Export bugs to markdown report."""
        if output_file is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_file = f"logs/bug_report_{timestamp}.md"
            
        output_path = Path(output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Bug Report\n\n")
            f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
            
            summary = self.get_summary()
            f.write("## Summary\n\n")
            f.write(f"- **Total Bugs**: {summary['total']}\n")
            f.write(f"- **By Severity**: {summary['by_severity']}\n")
            f.write(f"- **By Category**: {summary['by_category']}\n")
            f.write(f"- **By Status**: {summary['by_status']}\n\n")
            
            # Group by severity
            for severity in ["Critical", "High", "Medium", "Low"]:
                bugs = [b for b in self.bugs if b.severity == severity]
                if bugs:
                    f.write(f"## {severity} Priority ({len(bugs)})\n\n")
                    for bug in bugs:
                        f.write(f"### {bug.title}\n\n")
                        f.write(f"- **ID**: {bug.id}\n")
                        f.write(f"- **Component**: {bug.component or 'N/A'}\n")
                        f.write(f"- **Category**: {bug.category}\n")
                        f.write(f"- **Status**: {bug.status}\n")
                        f.write(f"- **Created**: {bug.created_at}\n\n")
                        f.write(f"{bug.description}\n\n")
                        
                        if bug.error_message:
                            f.write(f"**Error**: `{bug.error_message}`\n\n")
                            
                        if bug.reproduction_steps:
                            f.write("**Reproduction Steps**:\n")
                            for i, step in enumerate(bug.reproduction_steps, 1):
                                f.write(f"{i}. {step}\n")
                            f.write("\n")
                            
                        if bug.stack_trace:
                            f.write("**Stack Trace**:\n```\n")
                            f.write(bug.stack_trace)
                            f.write("\n```\n\n")
                            
                        f.write("---\n\n")
                        
        print(f"[BugTracker] Exported report to: {output_path}")
        return str(output_path)


# Global instance
_bug_tracker: Optional[BugTracker] = None


def get_bug_tracker() -> BugTracker:
    """Get or create global bug tracker."""
    global _bug_tracker
    if _bug_tracker is None:
        _bug_tracker = BugTracker()
    return _bug_tracker


def report_bug(title: str, description: str, **kwargs) -> Bug:
    """Convenience function to report a bug."""
    return get_bug_tracker().add_bug(title, description, **kwargs)


def capture_exception(title: str, exc: Exception, **kwargs) -> Bug:
    """Convenience function to capture exception."""
    return get_bug_tracker().capture_exception(title, exc, **kwargs)
