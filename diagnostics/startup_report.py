from __future__ import annotations

import importlib.util
import os
import shutil
import socket
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def timed_check(fn: Callable[[], Any]) -> tuple[bool, Any, float, str | None]:
    t0 = time.perf_counter()
    try:
        out = fn()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return True, out, latency_ms, None
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return False, None, latency_ms, str(e)


def service_checks(*, api_key_enabled: bool) -> dict:
    checks = []

    def db_ping():
        db_path = Path(__file__).resolve().parents[1] / "mem_db" / "data" / "documents.db"
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        version = cur.execute("select sqlite_version()").fetchone()[0]
        cur.execute("select 1").fetchone()
        con.close()
        return {"version": version, "path": str(db_path)}

    ok, details, latency, err = timed_check(db_ping)
    checks.append({"service": "database", "status": "Up" if ok else "Failed", "latency_ms": latency, "last_check": iso_now(), "details": details, "error": err})

    checks.append({
        "service": "api_endpoints",
        "status": "Up",
        "latency_ms": None,
        "last_check": iso_now(),
        "details": {
            "health": "/api/health",
            "startup_report": "/api/startup/report",
            "organization_stats": "/api/organization/stats",
        },
        "error": None,
    })

    checks.append({
        "service": "authentication",
        "status": "Enabled" if api_key_enabled else "Disabled",
        "latency_ms": None,
        "last_check": iso_now(),
        "details": {"api_key_required": api_key_enabled},
        "error": None,
    })

    checks.append({
        "service": "message_queue",
        "status": "Up" if module_available("agents.orchestration.message_bus") else "Failed",
        "latency_ms": None,
        "last_check": iso_now(),
        "details": {"type": "in_memory_message_bus"},
        "error": None if module_available("agents.orchestration.message_bus") else "message_bus module missing",
    })

    checks.append({
        "service": "external_integrations",
        "status": "NotConfigured",
        "latency_ms": None,
        "last_check": iso_now(),
        "details": {"critical_integrations": []},
        "error": None,
    })

    return {"items": checks}


def environment_snapshot() -> dict:
    load_1m = None
    try:
        load_1m = os.getloadavg()[0]
    except Exception:
        load_1m = None
    du = shutil.disk_usage(Path(__file__).resolve().parents[1])
    mem_total_mb = None
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            info = f.read()
        for line in info.splitlines():
            if line.startswith("MemTotal:"):
                mem_total_mb = round(int(line.split()[1]) / 1024, 2)
                break
    except Exception:
        mem_total_mb = None
    return {
        "host": socket.gethostname(),
        "python": os.sys.version.split()[0],
        "load_1m": load_1m,
        "mem_total_mb": mem_total_mb,
        "disk_total_gb": round(du.total / (1024**3), 2),
        "disk_free_gb": round(du.free / (1024**3), 2),
    }


def build_info() -> dict:
    commit = None
    branch = None
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    except Exception:
        pass
    return {"version": "1.0.0", "commit": commit, "branch": branch}


def migration_snapshot() -> dict:
    try:
        from mem_db.database import get_database_manager

        db = get_database_manager()
        items = db.schema_migration_status()
        failed = [x for x in items if not bool(x.get("success"))]
        return {"available": True, "count": len(items), "failed": failed, "items": items}
    except Exception as e:
        return {"available": False, "count": 0, "failed": [], "items": [], "error": str(e)}


def build_startup_report(
    *,
    app: Any,
    strict_startup: bool,
    required_production_agents: List[str],
    api_key_enabled: bool,
    rate_limit_requests_per_minute: int,
) -> dict:
    agent_state = getattr(app.state, "agent_startup", {}) or {}
    routers = getattr(app.state, "router_load_report", []) or []
    failed_critical = [r for r in routers if not r.get("ok") and not r.get("optional")]
    failed_optional = [r for r in routers if not r.get("ok") and r.get("optional")]
    startup_steps = []
    for step in (getattr(app.state, "startup_steps", []) or []):
        clean = {k: v for k, v in dict(step).items() if k != "_t0"}
        startup_steps.append(clean)

    return {
        "strict_startup": strict_startup,
        "required_production_agents": required_production_agents,
        "agents": agent_state,
        "routers": {
            "loaded": sum(1 for r in routers if r.get("ok")),
            "failed": failed_critical,
            "failed_optional": failed_optional,
            "total": len(routers),
        },
        "startup_steps": startup_steps,
        "services": service_checks(api_key_enabled=api_key_enabled),
        "environment": environment_snapshot(),
        "build": build_info(),
        "migrations": migration_snapshot(),
        "security": {
            "api_key_required": api_key_enabled,
            "rate_limiter": {
                "enabled": rate_limit_requests_per_minute > 0,
                "requests_per_minute": rate_limit_requests_per_minute,
            },
        },
        "runtime": {
            "startup_profile": getattr(app.state, "startup_profile", os.getenv("STARTUP_PROFILE", "full")),
            "agents_lazy_init": bool(getattr(app.state, "agents_lazy_init", False)),
            "startup_offline_safe": bool(getattr(app.state, "startup_offline_safe", False)),
        },
    }
