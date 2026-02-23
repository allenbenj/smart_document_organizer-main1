import sys
import os
from pathlib import Path
import json

# Add project root to path
root = Path(__file__).resolve().parents[2]
sys.path.append(str(root))

from scripts.utils.cluster_evidence import EvidenceClusterer
from gliner import GLiNER

def run_thematic_audit(file_path):
    print(f"--- STARTING AEDIS THEMATIC AUDIT: {file_path} ---")
    
    # 1. Multi-Format Text Extraction
    text = ""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(file_path)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    
    print(f"Extracted {len(text)} characters.")

    # 2. Strategic Clustering (Theme Discovery)
    print("\nPhase 1: Discovering Strategic Themes...")
    clusterer = EvidenceClusterer()
    clusters = clusterer.cluster_document(text, num_clusters=4)

    # 3. Multi-Task Oracle (Entity & Action Extraction)
    print("\nPhase 2: Deploying Multi-Task Oracle...")
    model_path = root / "models" / "gliner_zero_shot"
    oracle = GLiNER.from_pretrained(str(model_path.absolute()), local_files_only=True)
    
    # High-Resolution labels for this specific case
    labels = [
        "Prosecutor Name", 
        "Witness Name", 
        "Specific Misconduct Action", 
        "Case Citation", 
        "Legal Violation",
        "Evidence Document"
    ]

    # 4. Synthesize Results
    print("\n" + "="*70)
    print("AEDIS INTELLIGENCE REPORT: PROSECUTOR MISCONDUCT AUDIT")
    print("="*70)

    for cid, items in clusters.items():
        print(f"\n[STRATEGIC THEME {cid + 1}]")
        print("-" * 40)
        
        # Deploy Oracle on the Cluster Sample to "Identify" the cluster content
        theme_sample = "\n".join(items[:3])
        entities = oracle.predict_entities(theme_sample, labels, threshold=0.4)
        
        found_entities = {}
        for ent in entities:
            l, t = ent['label'], ent['text']
            if l not in found_entities: found_entities[l] = set()
            found_entities[l].add(t)

        if found_entities:
            print("KEY IDENTIFIERS FOUND:")
            for label, vals in found_entities.items():
                print(f"  • {label}: {', '.join(vals)}")
        
        print("\nLINKED EVIDENCE SNIPPETS:")
        for item in items[:3]: # Show top 3
            print(f"  > {item.strip()[:150]}...")

if __name__ == "__main__":
    target_file = r"E:\Organization_Folder\prosecutor-misconduct.txt"
    if os.path.exists(target_file):
        run_thematic_audit(target_file)
    else:
        print(f"Error: Could not find file at {target_file}")
