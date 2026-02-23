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

def test_local_gliner():
    # Use the specific local path
    model_path = str(root / "models" / "gliner")
    
    print(f"Attempting to load local model from: {model_path}")
    try:
        model = GLiNER.from_pretrained(model_path, local_files_only=True)
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Failed to load local model: {e}")
        return

    text = """
    The Brooklyn District Attorney’s Conviction Review Unit was created by District Attorney Charles Hines in 2011 
    and became far more active under his successor, Ken Thompson, who took office in 2014. 
    Retired police detective Louis Scarcella lied and fabricated evidence.
    """

    # Using labels directly from the robust ontology
    labels = ["Person", "Organization", "Court", "Prosecutor", "Witness", "Evidence Item", "Date"]
    
    print(f"\nTesting with ontology labels: {labels}")
    try:
        # Use very low threshold to see if it finds ANYTHING
        entities = model.predict_entities(text, labels, threshold=0.05)
        if not entities:
            print("No entities found even at 0.05 threshold.")
        for ent in entities:
            print(f"Found: {ent['text']} ({ent['label']}) [score: {ent['score']:.4f}]")
    except Exception as e:
        print(f"Prediction failed: {e}")

if __name__ == "__main__":
    test_local_gliner()
