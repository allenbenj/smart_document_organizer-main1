import os
import time
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

def track_changes(root_dir: str, hours: float = 1.0):
    """Scan the repository for files changed within the last X hours."""
    root = Path(root_dir).resolve()
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=hours)
    
    changes = []
    
    # Files to ignore
    ignore_dirs = {'.venv', '.git', '__pycache__', '.ruff_cache', '.pytest_cache', 'logs'}
    
    for path in root.rglob('*'):
        if any(part in ignore_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
            
        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        
        if mtime > threshold:
            changes.append({
                "file": str(path.relative_to(root)),
                "modified_at": mtime.isoformat(),
                "size_bytes": path.stat().st_size
            })
            
    # Sort by modification time (newest first)
    changes.sort(key=lambda x: x['modified_at'], reverse=True)
    
    report = {
        "scan_time": now.isoformat(),
        "lookback_hours": hours,
        "change_count": len(changes),
        "changes": changes
    }
    
    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Track project file changes via timestamps.")
    parser.add_argument("--hours", type=float, default=1.0, help="Number of hours to look back.")
    parser.add_argument("--output", type=str, default="logs/project_changes.json", help="Path to save the JSON report.")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).resolve().parents[2]
    report = track_changes(str(project_root), hours=args.hours)
    
    # Ensure logs dir exists
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    print(f"Detected {report['change_count']} changes in the last {args.hours} hours.")
    for change in report['changes']:
        print(f" - {change['file']} ({change['modified_at']})")
