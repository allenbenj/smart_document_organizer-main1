from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from services.data_integrity_service import DataIntegrityService


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_once(service: DataIntegrityService, output_path: Path | None) -> dict:
    report = service.generate_report()
    payload = {"generated_at": _utc_now(), "report": report}
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run data integrity checks.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports") / "data_integrity_report.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=0,
        help="If >0, run checks repeatedly on this interval.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of runs when interval-seconds > 0. Use 0 for infinite loop.",
    )
    args = parser.parse_args()

    service = DataIntegrityService()
    if args.interval_seconds <= 0:
        payload = run_once(service, args.output)
        print(json.dumps(payload, indent=2))
        return

    runs = 0
    while True:
        payload = run_once(service, args.output)
        print(json.dumps(payload, indent=2))
        runs += 1
        if args.iterations > 0 and runs >= args.iterations:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
