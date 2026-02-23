import sys
import os
import json
from pathlib import Path
import numpy as np
from sklearn.cluster import KMeans
import torch
from transformers import AutoTokenizer, AutoModel
import torch.nn.functional as F
import nltk
from nltk.tokenize import sent_tokenize

# Ensure NLTK data is present for sentence splitting
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# Add project root to path
root = Path(__file__).resolve().parents[2]
sys.path.append(str(root))

class EvidenceClusterer:
    def __init__(self, model_name="all-minilm-L6-v2"):
        # Resolve local path
        self.model_path = root / "models" / model_name
        if not self.model_path.exists():
            print(f"Warning: Local model {self.model_path} not found, using remote.")
            self.tokenizer = AutoTokenizer.from_pretrained(f"sentence-transformers/{model_name}")
            self.model = AutoModel.from_pretrained(f"sentence-transformers/{model_name}")
        else:
            print(f"Loading local weights via Transformers from: {self.model_path}")
            # Load locally from your files
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
            self.model = AutoModel.from_pretrained(str(self.model_path))
        
        self.model.eval()

    def _mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output[0] 
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def get_embeddings(self, sentences):
        """Generate high-fidelity embeddings using manual pooling."""
        encoded_input = self.tokenizer(sentences, padding=True, truncation=True, return_tensors='pt')
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        
        sentence_embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
        sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)
        return sentence_embeddings.numpy()

    def cluster_document(self, text, num_clusters=3):
        """Split text into sentences and group them by semantic similarity."""
        # 1. Tokenize into sentences
        raw_sentences = sent_tokenize(text)
        sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 25] 
        
        if len(sentences) < num_clusters:
            num_clusters = max(1, len(sentences))

        print(f"Processing {len(sentences)} sentences into {num_clusters} semantic clusters...")

        # 2. Generate Embeddings
        embeddings = self.get_embeddings(sentences)

        # 3. Perform KMeans Clustering
        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init='auto')
        kmeans.fit(embeddings)
        labels = kmeans.labels_

        # 4. Group results
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(sentences[i])

        return clusters

def main():
    # High-Resolution Test Case: Mixed Legal Scenarios
    sample_text = """
    An elected prosecutor who wants to change an established pattern of misconduct can exercise much tighter control. 
    The ADA's repeated delays in turning over relevant documents constitute violations of discovery rules. 
    Discovery rules ensure both sides can access necessary evidence for a fair trial. 
    Louis Scarcella lied and fabricated evidence in many murder cases. 
    The Brooklyn CIU has been responsible for 27 exonerations. 
    The defense of necessity may apply when an individual commits a criminal act during an emergency. 
    The defendant must reasonably have believed there was an actual and specific threat. 
    The harm caused by the criminal act must not be greater than the harm avoided.
    Brady rule mandates prosecutors to disclose all material and exculpatory evidence.
    Presenting false information to the grand jury is a serious violation of prosecutorial ethics.
    The necessity defense is sometimes called the lesser of two evils defense.
    A reasonable person would agree that an out of control bus is an actual threat to safety.
    """

    clusterer = EvidenceClusterer()
    results = clusterer.cluster_document(sample_text, num_clusters=3)

    print("\n" + "="*60)
    print("AEDIS STRATEGIC EVIDENCE CLUSTERING (all-MiniLM)")
    print("="*60)
    
    # Simple semantic labeling based on content keywords
    for cluster_id, items in results.items():
        print(f"\n[CLUSTER {cluster_id + 1}] - {len(items)} Semantic Links")
        print("-" * 40)
        for item in items:
            print(f" • {item}")

if __name__ == "__main__":
    main()
