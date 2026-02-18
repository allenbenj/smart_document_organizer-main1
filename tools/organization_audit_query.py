from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui.services.audit_store import OrganizationAuditStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Query organization_audit.db events.")
    parser.add_argument("--db", default="logs/organization_audit.db", help="Path to audit sqlite db")
    parser.add_argument("--limit", type=int, default=50, help="Number of rows to show")
    parser.add_argument(
        "--table",
        choices=["events", "cases"],
        default="cases",
        help="Which table to inspect (default: cases)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 1
    # Ensure latest schema exists before reading.
    OrganizationAuditStore(str(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if args.table == "events":
            rows = conn.execute(
                """
                SELECT id, event_type, payload_json, created_at
                FROM organization_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(args.limit)),),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, event_type, action, outcome, proposal_id, file_id,
                       current_path, recommended_folder, recommended_filename,
                       final_folder, final_filename, old_path, new_path,
                       note, error, payload_json, created_at
                FROM organization_learning_cases
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(args.limit)),),
            ).fetchall()
    finally:
        conn.close()

    for r in rows:
        payload = {}
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except Exception:
            payload = {"raw": r["payload_json"]}
        if args.table == "events":
            print(f"[{r['id']}] {r['created_at']} {r['event_type']}")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                f"[{r['id']}] {r['created_at']} {r['event_type']} "
                f"action={r['action']} outcome={r['outcome']} "
                f"proposal_id={r['proposal_id']} file_id={r['file_id']}"
            )
            print(
                f"old={r['old_path']} new={r['new_path']} "
                f"recommended={r['recommended_folder']}/{r['recommended_filename']} "
                f"final={r['final_folder']}/{r['final_filename']}"
            )
            if r["note"] or r["error"]:
                print(f"note={r['note']} error={r['error']}")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("-" * 60)
    if not rows:
        print(f"No rows found in table '{args.table}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
