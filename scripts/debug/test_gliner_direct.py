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

def test_gliner():
    # Use the public medium model
    model_path = "urchade/gliner_medium-v2.1"
    
    print(f"Loading model: {model_path}")
    try:
        model = GLiNER.from_pretrained(model_path)
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    text = """
    District Attorney Charles Hines created the unit in 2011. 
    Ken Thompson took office in 2014. 
    Retired police detective Louis Scarcella lied and fabricated evidence.
    The Brooklyn District Attorney's office is located in New York.
    """

    # Using highly descriptive, lowercase labels (best for GLiNER)
    labels = ["person name", "law enforcement agency", "court", "prosecutor", "law enforcement officer", "year", "city"]
    
    print(f"\nTesting with descriptive labels: {labels}")
    try:
        entities = model.predict_entities(text, labels, threshold=0.1)
        if not entities:
            print("No entities found at 0.1 threshold.")
        for ent in entities:
            print(f"Found: {ent['text']} ({ent['label']}) [score: {ent['score']:.4f}]")
    except Exception as e:
        print(f"Prediction failed: {e}")

if __name__ == "__main__":
    test_gliner()
