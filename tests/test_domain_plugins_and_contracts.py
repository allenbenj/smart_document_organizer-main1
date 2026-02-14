from services.domain_plugins import LabReportPluginTemplate, build_default_domain_plugin_registry
from services.extraction_contracts import (
    CURRENT_EXTRACTION_CONTRACT_VERSION,
    build_extraction_contract,
    migrate_contract_to_current,
    validate_extraction_contract,
)


def test_lab_report_plugin_template_detects_signals(tmp_path):
    p = tmp_path / "report.md"
    p.write_text("Lab Report\nTHC and CBD detected", encoding="utf-8")

    reg = build_default_domain_plugin_registry()
    plugin = reg.resolve(ext=".md", mime_type="text/markdown")
    assert isinstance(plugin, LabReportPluginTemplate)

    out = plugin.extract(p, text=p.read_text(encoding="utf-8"))
    tags = {s["tag"] for s in out["signals"]}
    assert "compound_thc" in tags
    assert "compound_cbd" in tags


def test_extraction_contract_versioning_migration():
    c = build_extraction_contract(kind="index_metadata", parser_name="markdown", payload={"a": 1})
    assert validate_extraction_contract(c) is True
    assert c["contract_version"] == CURRENT_EXTRACTION_CONTRACT_VERSION

    migrated = migrate_contract_to_current({"legacy_key": "v"})
    assert validate_extraction_contract(migrated) is True
    assert migrated["contract_version"] == CURRENT_EXTRACTION_CONTRACT_VERSION
