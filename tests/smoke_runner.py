import json
from datetime import datetime

try:
    from fastapi.testclient import TestClient
    from Start import app
except Exception as e:
    print(f"[FATAL] Import failed: {e}")
    raise SystemExit(1)

results = []


with TestClient(app) as client:
    def check(name, method, path, expected=(200,), json_body=None):
        try:
            r = client.get(path) if method == "GET" else client.post(path, json=json_body or {})
            ok = r.status_code in expected
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:300]}
            results.append({"name": name, "ok": ok, "status": r.status_code, "expected": expected, "path": path, "body": body})
        except Exception as e:
            results.append({"name": name, "ok": False, "status": None, "expected": expected, "path": path, "body": {"error": str(e)}})

    check("startup.report", "GET", "/api/startup/report")
    check("startup.services", "GET", "/api/startup/services")
    check("startup.environment", "GET", "/api/startup/environment")
    check("startup.migrations", "GET", "/api/startup/migrations")
    check("startup.control", "GET", "/api/startup/control")
    check("startup.retry.services", "POST", "/api/startup/control/retry-check", json_body={"check": "services"})
    check("startup.retry.environment", "POST", "/api/startup/control/retry-check", json_body={"check": "environment"})
    check("startup.retry.migrations", "POST", "/api/startup/control/retry-check", json_body={"check": "migrations"})
    check("startup.diagnostics.export", "GET", "/api/startup/diagnostics/export")
    check("startup.logs.tail", "GET", "/api/startup/logs/tail?lines=50")
    check("startup.awareness", "GET", "/api/startup/awareness?limit=20")

    check("organization.llm.status", "GET", "/api/organization/llm")
    check("organization.llm.switch.xai", "POST", "/api/organization/llm/switch", json_body={"provider": "xai"})
    check("organization.llm.switch.invalid", "POST", "/api/organization/llm/switch", expected=(400,), json_body={"provider": "bad-provider"})
    check("organization.generate", "POST", "/api/organization/proposals/generate", json_body={"limit": 10})
    check("organization.list", "GET", "/api/organization/proposals?limit=10&offset=0")
    check("organization.apply.dryrun", "POST", "/api/organization/apply", json_body={"limit": 10, "dry_run": True})

passed = sum(1 for r in results if r["ok"])
total = len(results)

print("\n=== SMOKE TEST REPORT ===")
print(f"Time: {datetime.now().isoformat()}")
print(f"Passed: {passed}/{total}\n")

for r in results:
    print(f"[{'PASS' if r['ok'] else 'FAIL'}] {r['name']} -> {r['status']} ({r['path']})")
    if not r["ok"]:
        print("      body:", json.dumps(r["body"], default=str)[:500])

diag = next((x for x in results if x["name"] == "startup.diagnostics.export"), None)
if diag and isinstance(diag["body"], dict):
    print("\ndiagnostics has config_digest:", "config_digest" in diag["body"])
    print("diagnostics has awareness_events:", "awareness_events" in diag["body"])

# Self-diagnose common 503 cause for org routes (strict DI/service container unavailable)
org_failures = [
    r for r in results
    if r["name"].startswith("organization.") and not r["ok"] and r.get("status") == 503
]
if org_failures:
    print("\n=== ORGANIZATION 503 DIAGNOSTICS ===")
    sr = next((x for x in results if x["name"] == "startup.report"), None)
    if sr and isinstance(sr.get("body"), dict):
        body = sr["body"]
        report = body.get("report") if isinstance(body.get("report"), dict) else {}
        readiness = report.get("readiness") if isinstance(report.get("readiness"), dict) else {}
        agents = report.get("agents") if isinstance(report.get("agents"), dict) else {}
        steps = report.get("startup_steps") if isinstance(report.get("startup_steps"), list) else []
        failed_steps = [s for s in steps if str(s.get("status", "")).lower() == "failed"]

        print("readiness.ok:", readiness.get("ok"))
        print("strict_router_failure:", readiness.get("strict_router_failure"))
        print("missing_required_agents:", readiness.get("missing_required_agents"))
        print("agents.available:", agents.get("available"))
        print("agents.missing:", agents.get("missing"))
        print("agents.memory_ready:", agents.get("memory_ready"))

        if failed_steps:
            print("failed_startup_steps:")
            for s in failed_steps:
                print(" -", s.get("name"), "| error:", s.get("error"))
        else:
            print("failed_startup_steps: []")
    else:
        print("startup.report unavailable; cannot extract readiness diagnostics")

raise SystemExit(0 if passed == total else 2)
