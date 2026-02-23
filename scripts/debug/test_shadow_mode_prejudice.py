import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parents[2]
sys.path.append(str(root))

from agents.legal.legal_reasoning_engine import LegalReasoningEngine, ReasoningFramework
from core.container.service_container_impl import ProductionServiceContainer
from core.container import bootstrap
from agents.extractors.legal_entity_extractor import create_legal_entity_extractor

async def test_shadow_mode_on_prejudice_file():
    print("--- INITIATING AEDIS STRATEGIC SHADOW MODE TEST ---")
    
    # 1. Setup & Bootstrap Environment
    container = ProductionServiceContainer()
    await bootstrap.configure(container, app=None)
    
    # MANUALLY REGISTER THE EXTRACTOR FOR THIS TEST
    extractor = await create_legal_entity_extractor(container)
    await container.register_instance(type(extractor), extractor, aliases=["entity_extractor"])
    
    engine = LegalReasoningEngine(service_container=container)
    
    # 2. Load the target document
    file_path = Path(r"E:\Organization_Folder\02_Working_Folder\02_Analysis\05_Case Analysis\Establish_Prejudice_Bias_Analysis_2025-05-06.md")
    
    if not file_path.exists():
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"Analyzing: {file_path.name} ({len(content)} chars)")

    # 3. Run Adversarial Analysis
    result = await engine.analyze_legal_document(
        document_content=content,
        document_id="PREJUDICE_AUDIT_001",
        analysis_type="adversarial",
        reasoning_framework=ReasoningFramework.IRAC
    )

    # 4. Display the Results
    print("\n" + "="*70)
    print("AEDIS STRATEGIC INTELLIGENCE REPORT: SHADOW MODE AUDIT")
    print("="*70)

    print("\n[ADVERSARIAL PERSPECTIVES]")
    for rec in result.recommendations:
        if any(kw in rec for kw in ["State Theory", "Defense Move", "Shadow Mode", "Jurisdiction"]):
            print(f" {rec}")

    print("\n[FACT-DERIVED LEGAL ISSUES (GROUNDED)]")
    if not result.legal_issues:
        print(" (No grounded issues found with current entity/NLI thresholds)")
    for issue in result.legal_issues:
        print(f"\nID: {issue.issue_id}")
        print(f"Question: {issue.description}")
        print(f"Confidence (NLI Verified): {issue.confidence:.2f}")
        if issue.entities_involved:
            print(f"Primary Party: {issue.entities_involved[0]['text']}")

    print("\n" + "="*70)
    print("END OF STRATEGIC REPORT")

if __name__ == "__main__":
    asyncio.run(test_shadow_mode_on_prejudice_file())
