param(
  [ValidateSet('h1','p0','p1','p2','p3','p4','p5','p6','p7','p8')]
  [string]$Phase = 'h1',
  [string]$GateDbPath = ''
)

$ErrorActionPreference = 'Stop'
$ts = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runDir = Join-Path 'logs' ("ael_${Phase}_${ts}")
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
$PythonCmd = $null
$GateDbPathResolved = if ($GateDbPath) { $GateDbPath } else { Join-Path $runDir 'gate_documents.db' }
$DefaultDbPath = Join-Path 'mem_db/data' 'documents.db'

function Resolve-PythonCommand {
  foreach ($candidate in @('python', 'py', 'python3')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
      return $candidate
    }
  }
  throw '[AEL] no python executable found (tried: python, py, python3)'
}

function Invoke-Step {
  param([string]$Label, [scriptblock]$Action)
  Write-Host "[AEL][$Phase] $Label"
  & $Action
}

$PythonCmd = Resolve-PythonCommand
Write-Host "[AEL] using python command: $PythonCmd"

function Initialize-GateDb {
  if (-not $GateDbPath -and (Test-Path -LiteralPath $DefaultDbPath)) {
    Copy-Item -LiteralPath $DefaultDbPath -Destination $GateDbPathResolved -Force
    Write-Host "[AEL] gate DB cloned: $GateDbPathResolved"
  } else {
    $parent = Split-Path -Path $GateDbPathResolved -Parent
    if ($parent) {
      New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Write-Host "[AEL] using gate DB path: $GateDbPathResolved"
    New-Item -Path $GateDbPathResolved -ItemType File -Force | Out-Null
  }
}

function Check-FileExists {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "[AEL] missing artifact: $Path"
  }
}

function Check-JsonFieldEq {
  param([string]$Path, [string]$Key, [string]$Expected)
  $obj = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
  $value = [string]$obj.$Key
  if ($value -ne $Expected) {
    throw "$Path expected $Key=$Expected got $value"
  }
}

function Check-JsonFieldIntEq {
  param([string]$Path, [string]$Key, [int]$Expected)
  $obj = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
  $value = [int]$obj.$Key
  if ($value -ne $Expected) {
    throw "$Path expected $Key=$Expected got $value"
  }
}

function Check-JunitExecuted {
  param([string]$Path)
  [xml]$doc = Get-Content -LiteralPath $Path -Raw
  $total = 0
  if ($doc.testsuite) {
    $total = [int]$doc.testsuite.tests
  }
  if ($doc.testsuites) {
    foreach ($suite in $doc.testsuites.testsuite) {
      $total += [int]$suite.tests
    }
  }
  if ($total -le 0) {
    throw "$Path has 0 executed tests"
  }
}

function Run-PytestGate {
  param([string]$TestPath, [string]$JunitPath)
  if (-not (Test-Path -LiteralPath $TestPath)) {
    throw "[AEL] missing test target: $TestPath"
  }
  Invoke-Step "pytest $TestPath" { & pytest $TestPath -q "--junitxml=$JunitPath" }
  Check-FileExists -Path $JunitPath
  Check-JunitExecuted -Path $JunitPath
}

function Run-IntegrityGate {
  param([string]$Layer, [string]$Out)
  Invoke-Step "integrity layer=$Layer" { & $PythonCmd Start.py --check-integrity --layer $Layer --output $Out }
  Check-FileExists -Path $Out
  Check-JsonFieldEq -Path $Out -Key 'status' -Expected 'pass'
}

function Run-ForbiddenScanGate {
  param([string]$Out)
  Invoke-Step 'forbidden runtime scan' { & $PythonCmd scripts/quality/forbidden_runtime_scan.py --paths agents services routes --output $Out }
  Check-FileExists -Path $Out
  Check-JsonFieldEq -Path $Out -Key 'status' -Expected 'pass'
  Check-JsonFieldIntEq -Path $Out -Key 'violations' -Expected 0
}

function Run-MigrationGateIfPresent {
  param([string]$PhaseName)
  if (-not (Test-Path -LiteralPath 'scripts/migrate.py')) {
    throw "[AEL] scripts/migrate.py not found; migration gate cannot run for $PhaseName"
  }
  Invoke-Step "migration up phase=$PhaseName" {
    & $PythonCmd scripts/migrate.py up --phase $PhaseName --db-path $GateDbPathResolved --retries 4 --retry-delay-ms 500 --report (Join-Path $runDir "migrate_${PhaseName}_up.json")
  }
  Invoke-Step "migration down phase=$PhaseName" {
    & $PythonCmd scripts/migrate.py down --phase $PhaseName --db-path $GateDbPathResolved --retries 4 --retry-delay-ms 500 --report (Join-Path $runDir "migrate_${PhaseName}_down.json")
  }
  Invoke-Step "migration redo-verify phase=$PhaseName" {
    & $PythonCmd scripts/migrate.py redo --phase $PhaseName --db-path $GateDbPathResolved --verify-data-integrity --retries 4 --retry-delay-ms 500 --report (Join-Path $runDir "migrate_${PhaseName}_redo_verify.json")
  }
}

Initialize-GateDb

switch ($Phase) {
  'h1' {
    Run-IntegrityGate -Layer 'h1' -Out (Join-Path $runDir 'integrity_h1.json')
    Run-ForbiddenScanGate -Out (Join-Path $runDir 'forbidden_runtime_scan_h1.json')
    Run-PytestGate -TestPath 'tests/test_document_processing.py' -JunitPath (Join-Path $runDir 'junit_h1_doc_processing.xml')
    Run-PytestGate -TestPath 'tests/test_organization_integration.py' -JunitPath (Join-Path $runDir 'junit_h1_org_integration.xml')
    Run-PytestGate -TestPath 'tests/test_organization_route_contracts.py' -JunitPath (Join-Path $runDir 'junit_h1_org_contracts.xml')
  }
  'p0' {
    Run-IntegrityGate -Layer 'p0_contracts' -Out (Join-Path $runDir 'integrity_p0_contracts.json')
    Run-PytestGate -TestPath 'tests/quality/test_no_runtime_stubs.py' -JunitPath (Join-Path $runDir 'junit_p0_no_stubs.xml')
    Run-PytestGate -TestPath 'tests/contracts/test_aedis_models.py' -JunitPath (Join-Path $runDir 'junit_p0_contracts.xml')
    Run-PytestGate -TestPath 'tests/test_gui_api_contract_alignment.py' -JunitPath (Join-Path $runDir 'junit_p0_gui_alignment.xml')
  }
  'p1' {
    Run-IntegrityGate -Layer 'canonical' -Out (Join-Path $runDir 'integrity_p1_canonical.json')
    Run-PytestGate -TestPath 'tests/test_canonical_immutability.py' -JunitPath (Join-Path $runDir 'junit_p1_immutability.xml')
    Run-PytestGate -TestPath 'tests/test_canonical_lineage_integrity.py' -JunitPath (Join-Path $runDir 'junit_p1_lineage.xml')
    Run-PytestGate -TestPath 'tests/test_gui_canonical_workflow.py' -JunitPath (Join-Path $runDir 'junit_p1_gui.xml')
    Run-MigrationGateIfPresent -PhaseName 'p1'
    Run-PytestGate -TestPath 'tests/migrations/test_phase1_backfill.py' -JunitPath (Join-Path $runDir 'junit_p1_backfill.xml')
  }
  'p2' {
    Run-IntegrityGate -Layer 'ontology' -Out (Join-Path $runDir 'integrity_p2_ontology.json')
    Run-PytestGate -TestPath 'tests/test_ontology_registry_versions.py' -JunitPath (Join-Path $runDir 'junit_p2_versions.xml')
    Run-PytestGate -TestPath 'tests/test_ontology_registry_activation.py' -JunitPath (Join-Path $runDir 'junit_p2_activation.xml')
    Run-PytestGate -TestPath 'tests/test_gui_ontology_registry_workflow.py' -JunitPath (Join-Path $runDir 'junit_p2_gui.xml')
    Run-MigrationGateIfPresent -PhaseName 'p2'
    Run-PytestGate -TestPath 'tests/migrations/test_phase2_backfill.py' -JunitPath (Join-Path $runDir 'junit_p2_backfill.xml')
  }
  'p3' {
    Run-IntegrityGate -Layer 'provenance' -Out (Join-Path $runDir 'integrity_p3_provenance.json')
    Run-PytestGate -TestPath 'tests/test_provenance_required_fields.py' -JunitPath (Join-Path $runDir 'junit_p3_required_fields.xml')
    Run-PytestGate -TestPath 'tests/test_provenance_trace_reconstruction.py' -JunitPath (Join-Path $runDir 'junit_p3_trace.xml')
    Run-PytestGate -TestPath 'tests/test_gui_provenance_highlighting.py' -JunitPath (Join-Path $runDir 'junit_p3_gui_highlight.xml')
    Run-MigrationGateIfPresent -PhaseName 'p3'
  }
  'p4' {
    Run-IntegrityGate -Layer 'planner_judge' -Out (Join-Path $runDir 'integrity_p4_planner_judge.json')
    Run-PytestGate -TestPath 'tests/test_planner_judge_gate.py' -JunitPath (Join-Path $runDir 'junit_p4_gate.xml')
    Run-PytestGate -TestPath 'tests/test_judge_determinism.py' -JunitPath (Join-Path $runDir 'junit_p4_determinism.xml')
    Run-PytestGate -TestPath 'tests/test_judge_ruleset_versioning.py' -JunitPath (Join-Path $runDir 'junit_p4_ruleset.xml')
    Run-PytestGate -TestPath 'tests/test_gui_planner_judge_workflow.py' -JunitPath (Join-Path $runDir 'junit_p4_gui.xml')
  }
  'p5' {
    Run-IntegrityGate -Layer 'heuristics' -Out (Join-Path $runDir 'integrity_p5_heuristics.json')
    Run-PytestGate -TestPath 'tests/test_heuristic_promotion_thresholds.py' -JunitPath (Join-Path $runDir 'junit_p5_thresholds.xml')
    Run-PytestGate -TestPath 'tests/test_heuristic_collision_detection.py' -JunitPath (Join-Path $runDir 'junit_p5_collision.xml')
    Run-PytestGate -TestPath 'tests/test_gui_heuristic_governance.py' -JunitPath (Join-Path $runDir 'junit_p5_gui.xml')
  }
  'p6' {
    Run-IntegrityGate -Layer 'generative_instructional' -Out (Join-Path $runDir 'integrity_p6_gen_instr.json')
    Run-PytestGate -TestPath 'tests/test_generation_requires_judge_pass.py' -JunitPath (Join-Path $runDir 'junit_p6_gen_gate.xml')
    Run-PytestGate -TestPath 'tests/test_learning_path_traceability.py' -JunitPath (Join-Path $runDir 'junit_p6_learning_trace.xml')
    Run-PytestGate -TestPath 'tests/test_gui_learning_mode.py' -JunitPath (Join-Path $runDir 'junit_p6_gui.xml')
  }
  'p7' {
    Run-IntegrityGate -Layer 'ontology_enforcement' -Out (Join-Path $runDir 'integrity_p7_ontology_enforcement.json')
    Run-PytestGate -TestPath 'tests/test_entity_ontology_enforcement_global.py' -JunitPath (Join-Path $runDir 'junit_p7_enforcement.xml')
    Run-PytestGate -TestPath 'tests/test_entity_type_extension_registration.py' -JunitPath (Join-Path $runDir 'junit_p7_extensions.xml')
    Run-PytestGate -TestPath 'tests/test_gui_entity_ontology_alignment.py' -JunitPath (Join-Path $runDir 'junit_p7_gui.xml')
  }
  'p8' {
    Run-IntegrityGate -Layer 'measurement' -Out (Join-Path $runDir 'integrity_p8_measurement.json')
    Run-PytestGate -TestPath 'tests/test_evaluation_metrics_pipeline.py' -JunitPath (Join-Path $runDir 'junit_p8_metrics.xml')
    Run-PytestGate -TestPath 'tests/test_holdout_guardrails.py' -JunitPath (Join-Path $runDir 'junit_p8_holdout.xml')
    Run-PytestGate -TestPath 'tests/test_gui_kpi_dashboard.py' -JunitPath (Join-Path $runDir 'junit_p8_gui.xml')
  }
}

Write-Host "AEL gate run completed phase=$Phase artifacts=$runDir"
