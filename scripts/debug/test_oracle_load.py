import sys
import os
from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parents[2]
sys.path.append(str(root))

try:
    from gliner import GLiNER
    import torch
    print(f"GLiNER imported. Torch version: {torch.__version__}")
except ImportError:
    print("GLiNER not installed.")
    sys.exit(1)

def test_gliner_oracle():
    # Use the new Multi-Task Oracle path
    model_path = str(root / "models" / "gliner_zero_shot")
    
    print(f"Loading Multi-Task Oracle from: {model_path}")
    try:
        model = GLiNER.from_pretrained(model_path, local_files_only=True)
        print("Oracle loaded successfully.")
    except Exception as e:
        print(f"Failed to load Oracle: {e}")
        return

    text = """
    District Attorney Charles Hines created the unit in 2011. 
    Ken Thompson took office in 2014. 
    Retired police detective Louis Scarcella lied and fabricated evidence.
    The Brooklyn District Attorney's office is located in New York.
    """

    # Testing the Oracle's Multi-Task capability with descriptive labels
    labels = [
        "Person", 
        "Organization", 
        "Law Enforcement Officer", 
        "The date someone took office", 
        "Action of fabricating evidence",
        "City"
    ]
    
    print(f"\nTesting Oracle with Multi-Task labels: {labels}")
    try:
        # Higher threshold for this large model
        entities = model.predict_entities(text, labels, threshold=0.4)
        if not entities:
            print("No entities found.")
        for ent in entities:
            text_found = ent.get('text', 'N/A')
            label_found = ent.get('label', 'N/A')
            score_found = ent.get('score', 0.0)
            print(f"Found: {text_found} ({label_found}) [score: {score_found:.4f}]")
    except Exception as e:
        print(f"Oracle prediction failed: {e}")

if __name__ == "__main__":
    test_gliner_oracle()
