#!/usr/bin/env bash
set -euo pipefail

PHASE="${1:-h1}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="logs/ael_${PHASE}_${TS}"
mkdir -p "${RUN_DIR}"
GATE_DB_PATH="${RUN_DIR}/gate_documents.db"
DEFAULT_DB_PATH="mem_db/data/documents.db"
if [[ -n "${AEL_GATE_DB_PATH:-}" ]]; then
  GATE_DB_PATH="${AEL_GATE_DB_PATH}"
fi

if [[ "${GATE_DB_PATH}" == "${RUN_DIR}/gate_documents.db" && -f "${DEFAULT_DB_PATH}" ]]; then
  cp -f "${DEFAULT_DB_PATH}" "${GATE_DB_PATH}"
  echo "[AEL] gate DB cloned: ${GATE_DB_PATH}"
else
  mkdir -p "$(dirname "${GATE_DB_PATH}")"
  : > "${GATE_DB_PATH}"
  echo "[AEL] using gate DB path: ${GATE_DB_PATH}"
fi

check_file_exists() {
  local file_path="$1"
  if [[ ! -f "${file_path}" ]]; then
    echo "[AEL] missing artifact: ${file_path}" >&2
    exit 10
  fi
}

check_json_field_eq() {
  local file_path="$1"
  local key="$2"
  local expected="$3"
  python3 - "$file_path" "$key" "$expected" <<'PY'
import json
import sys

p, key, expected = sys.argv[1], sys.argv[2], sys.argv[3]
with open(p, "r", encoding="utf-8") as fh:
    obj = json.load(fh)
val = str(obj.get(key, ""))
if val != expected:
    raise SystemExit(f"{p}: expected {key}={expected}, got {val}")
PY
}

check_json_field_int_eq() {
  local file_path="$1"
  local key="$2"
  local expected="$3"
  python3 - "$file_path" "$key" "$expected" <<'PY'
import json
import sys

p, key, expected = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(p, "r", encoding="utf-8") as fh:
    obj = json.load(fh)
val = int(obj.get(key, -999999))
if val != expected:
    raise SystemExit(f"{p}: expected {key}={expected}, got {val}")
PY
}

check_junit_executed() {
  local xml_path="$1"
  python3 - "$xml_path" <<'PY'
import sys
import xml.etree.ElementTree as ET

path = sys.argv[1]
tree = ET.parse(path)
root = tree.getroot()

if root.tag == "testsuite":
    suites = [root]
else:
    suites = root.findall("testsuite")

if not suites:
    raise SystemExit(f"{path}: no testsuite nodes")

total = 0
for suite in suites:
    total += int(suite.attrib.get("tests", 0))

if total <= 0:
    raise SystemExit(f"{path}: 0 tests executed")
PY
}

run_pytest_gate() {
  local test_path="$1"
  local junit_path="$2"
  if [[ ! -f "${test_path}" ]]; then
    echo "[AEL] missing test target: ${test_path}" >&2
    exit 11
  fi
  pytest "${test_path}" -q --junitxml="${junit_path}"
  check_file_exists "${junit_path}"
  check_junit_executed "${junit_path}"
}

run_integrity_gate() {
  local layer="$1"
  local out="$2"
  python3 Start.py --check-integrity --layer "${layer}" --output "${out}"
  check_file_exists "${out}"
  check_json_field_eq "${out}" "status" "pass"
}

run_forbidden_scan_gate() {
  local out="$1"
  python3 scripts/quality/forbidden_runtime_scan.py --paths agents services routes --output "${out}"
  check_file_exists "${out}"
  check_json_field_eq "${out}" "status" "pass"
  check_json_field_int_eq "${out}" "violations" "0"
}

run_migration_gate_if_present() {
  local phase="$1"
  if [[ ! -f scripts/migrate.py ]]; then
    echo "[AEL] scripts/migrate.py not found; migration gate cannot run for ${phase}" >&2
    exit 12
  fi
  python3 scripts/migrate.py up --phase "${phase}" --db-path "${GATE_DB_PATH}" --retries 4 --retry-delay-ms 500 --report "${RUN_DIR}/migrate_${phase}_up.json"
  check_file_exists "${RUN_DIR}/migrate_${phase}_up.json"
  python3 scripts/migrate.py down --phase "${phase}" --db-path "${GATE_DB_PATH}" --retries 4 --retry-delay-ms 500 --report "${RUN_DIR}/migrate_${phase}_down.json"
  check_file_exists "${RUN_DIR}/migrate_${phase}_down.json"
  python3 scripts/migrate.py redo --phase "${phase}" --db-path "${GATE_DB_PATH}" --verify-data-integrity --retries 4 --retry-delay-ms 500 --report "${RUN_DIR}/migrate_${phase}_redo_verify.json"
  check_file_exists "${RUN_DIR}/migrate_${phase}_redo_verify.json"
}

case "${PHASE}" in
  h1)
    run_integrity_gate "h1" "${RUN_DIR}/integrity_h1.json"
    run_forbidden_scan_gate "${RUN_DIR}/forbidden_runtime_scan_h1.json"
    run_pytest_gate "tests/test_document_processing.py" "${RUN_DIR}/junit_h1_doc_processing.xml"
    run_pytest_gate "tests/test_organization_integration.py" "${RUN_DIR}/junit_h1_org_integration.xml"
    run_pytest_gate "tests/test_organization_route_contracts.py" "${RUN_DIR}/junit_h1_org_contracts.xml"
    ;;
  p0)
    run_integrity_gate "p0_contracts" "${RUN_DIR}/integrity_p0_contracts.json"
    run_pytest_gate "tests/quality/test_no_runtime_stubs.py" "${RUN_DIR}/junit_p0_no_stubs.xml"
    run_pytest_gate "tests/contracts/test_aedis_models.py" "${RUN_DIR}/junit_p0_contracts.xml"
    run_pytest_gate "tests/test_gui_api_contract_alignment.py" "${RUN_DIR}/junit_p0_gui_alignment.xml"
    ;;
  p1)
    run_integrity_gate "canonical" "${RUN_DIR}/integrity_p1_canonical.json"
    run_pytest_gate "tests/test_canonical_immutability.py" "${RUN_DIR}/junit_p1_immutability.xml"
    run_pytest_gate "tests/test_canonical_lineage_integrity.py" "${RUN_DIR}/junit_p1_lineage.xml"
    run_pytest_gate "tests/test_gui_canonical_workflow.py" "${RUN_DIR}/junit_p1_gui.xml"
    run_migration_gate_if_present "p1"
    run_pytest_gate "tests/migrations/test_phase1_backfill.py" "${RUN_DIR}/junit_p1_backfill.xml"
    ;;
  p2)
    run_integrity_gate "ontology" "${RUN_DIR}/integrity_p2_ontology.json"
    run_pytest_gate "tests/test_ontology_registry_versions.py" "${RUN_DIR}/junit_p2_versions.xml"
    run_pytest_gate "tests/test_ontology_registry_activation.py" "${RUN_DIR}/junit_p2_activation.xml"
    run_pytest_gate "tests/test_gui_ontology_registry_workflow.py" "${RUN_DIR}/junit_p2_gui.xml"
    run_migration_gate_if_present "p2"
    run_pytest_gate "tests/migrations/test_phase2_backfill.py" "${RUN_DIR}/junit_p2_backfill.xml"
    ;;
  p3)
    run_integrity_gate "provenance" "${RUN_DIR}/integrity_p3_provenance.json"
    run_pytest_gate "tests/test_provenance_required_fields.py" "${RUN_DIR}/junit_p3_required_fields.xml"
    run_pytest_gate "tests/test_provenance_trace_reconstruction.py" "${RUN_DIR}/junit_p3_trace.xml"
    run_pytest_gate "tests/test_gui_provenance_highlighting.py" "${RUN_DIR}/junit_p3_gui_highlight.xml"
    run_migration_gate_if_present "p3"
    ;;
  p4)
    run_integrity_gate "planner_judge" "${RUN_DIR}/integrity_p4_planner_judge.json"
    run_pytest_gate "tests/test_planner_judge_gate.py" "${RUN_DIR}/junit_p4_gate.xml"
    run_pytest_gate "tests/test_judge_determinism.py" "${RUN_DIR}/junit_p4_determinism.xml"
    run_pytest_gate "tests/test_judge_ruleset_versioning.py" "${RUN_DIR}/junit_p4_ruleset.xml"
    run_pytest_gate "tests/test_gui_planner_judge_workflow.py" "${RUN_DIR}/junit_p4_gui.xml"
    ;;
  p5)
    run_integrity_gate "heuristics" "${RUN_DIR}/integrity_p5_heuristics.json"
    run_pytest_gate "tests/test_heuristic_promotion_thresholds.py" "${RUN_DIR}/junit_p5_thresholds.xml"
    run_pytest_gate "tests/test_heuristic_collision_detection.py" "${RUN_DIR}/junit_p5_collision.xml"
    run_pytest_gate "tests/test_gui_heuristic_governance.py" "${RUN_DIR}/junit_p5_gui.xml"
    ;;
  p6)
    run_integrity_gate "generative_instructional" "${RUN_DIR}/integrity_p6_gen_instr.json"
    run_pytest_gate "tests/test_generation_requires_judge_pass.py" "${RUN_DIR}/junit_p6_gen_gate.xml"
    run_pytest_gate "tests/test_learning_path_traceability.py" "${RUN_DIR}/junit_p6_learning_trace.xml"
    run_pytest_gate "tests/test_gui_learning_mode.py" "${RUN_DIR}/junit_p6_gui.xml"
    ;;
  p7)
    run_integrity_gate "ontology_enforcement" "${RUN_DIR}/integrity_p7_ontology_enforcement.json"
    run_pytest_gate "tests/test_entity_ontology_enforcement_global.py" "${RUN_DIR}/junit_p7_enforcement.xml"
    run_pytest_gate "tests/test_entity_type_extension_registration.py" "${RUN_DIR}/junit_p7_extensions.xml"
    run_pytest_gate "tests/test_gui_entity_ontology_alignment.py" "${RUN_DIR}/junit_p7_gui.xml"
    ;;
  p8)
    run_integrity_gate "measurement" "${RUN_DIR}/integrity_p8_measurement.json"
    run_pytest_gate "tests/test_evaluation_metrics_pipeline.py" "${RUN_DIR}/junit_p8_metrics.xml"
    run_pytest_gate "tests/test_holdout_guardrails.py" "${RUN_DIR}/junit_p8_holdout.xml"
    run_pytest_gate "tests/test_gui_kpi_dashboard.py" "${RUN_DIR}/junit_p8_gui.xml"
    ;;
  *)
    echo "Unknown phase '${PHASE}'. Use one of: h1 p0 p1 p2 p3 p4 p5 p6 p7 p8" >&2
    exit 2
    ;;
esac

echo "AEL gate run completed for phase=${PHASE} artifacts=${RUN_DIR}"
