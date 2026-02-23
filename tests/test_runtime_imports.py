import traceback
import sys

sys.path.insert(0, '.')

modules_to_test = [
    ("EnhancedAgentFactory", "agents.base.enhanced_agent_factory", "EnhancedAgentFactory"),
    ("create_legal_entity_extractor", "agents.extractors.entity_extractor", "create_legal_entity_extractor"),
    ("create_irac_analyzer", "agents.legal.irac_analyzer", "create_irac_analyzer"),
    ("create_legal_reasoning_engine", "agents.legal.legal_reasoning_engine", "create_legal_reasoning_engine"),
    ("create_document_processor", "agents.processors.document_processor", "create_document_processor"),
    ("ProductionServiceContainer", "core.container.service_container_impl", "ProductionServiceContainer"),
    ("ToulminAnalyzer", "agents.legal.toulmin_analyzer", "ToulminAnalyzer"),
]

for name, module_path, attr in modules_to_test:
    try:
        mod = __import__(module_path, fromlist=[attr])
        obj = getattr(mod, attr)
        print(f"[OK] {name}: SUCCESS")
    except Exception as e:
        print(f"[FAIL] {name}: FAILED - {e}")
        if "attempted relative import" in str(e):
            print(f"  >>> This is the problematic module!")
            traceback.print_exc()
