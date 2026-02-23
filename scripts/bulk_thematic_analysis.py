
import os
import sys
import json
from pathlib import Path
import docx2txt
import PyPDF2
from datetime import datetime
import nltk
from nltk.tokenize import sent_tokenize

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.utils.evidence_clusterer import EvidenceClusterer

def extract_text(file_path):
    ext = Path(file_path).suffix.lower()
    try:
        if ext == ".txt" or ext == ".md":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif ext == ".docx":
            return docx2txt.process(file_path)
        elif ext == ".pdf":
            text = ""
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n"
            return text
    except Exception as e:
        print(f"Error extracting {file_path}: {e}")
    return ""

def main():
    target_dir = "/mnt/e/Organization_Folder/02_Working_Folder/02_Analysis/08_Interviews"
    print(f"Starting Bounded Bulk Thematic Analysis for: {target_dir}")
    
    all_text = []
    files = list(Path(target_dir).glob("*"))
    print(f"Found {len(files)} files.")
    
    for f in files:
        if f.is_file():
            print(f"Extracting: {f.name}")
            content = extract_text(str(f))
            if content.strip():
                all_text.append(f"--- FILE: {f.name} ---\n{content}")
    
    full_corpus = "\n\n".join(all_text)
    if not full_corpus.strip():
        print("No text extracted.")
        return

    # Bounded sentence tokenization to avoid memory overflow
    print("Tokenizing sentences...")
    all_sentences = sent_tokenize(full_corpus)
    print(f"Total sentences: {len(all_sentences)}")
    
    # Take a representative sample if too large
    limit = 3000
    if len(all_sentences) > limit:
        print(f"Limiting to first {limit} sentences for memory safety.")
        sentences_to_cluster = all_sentences[:limit]
    else:
        sentences_to_cluster = all_sentences

    print("Initializing Clusterer...")
    clusterer = EvidenceClusterer()
    
    # We skip the internal tokenization of clusterer by passing sentences if we can, 
    # but evidence_clusterer.py expects 'text' and does its own tokenization.
    # Let's re-join the bounded set.
    bounded_text = "\n".join(sentences_to_cluster)

    num_clusters = 7
    print(f"Clustering corpus into {num_clusters} themes...")
    clusters = clusterer.cluster_document(bounded_text, num_clusters=num_clusters)
    
    # Generate Report
    report_dir = Path("documents/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "Bulk_Interviews_Thematic_Analysis.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# AEDIS Bulk Thematic Analysis Report (Bounded)\n")
        f.write(f"**Source Folder**: {target_dir}\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total Files Processed**: {len(all_text)}\n")
        f.write(f"**Total Sentences in Files**: {len(all_sentences)}\n")
        f.write(f"**Sentences Analyzed**: {len(sentences_to_cluster)}\n")
        f.write("=" * 40 + "\n\n")
        
        for i, items in clusters.items():
            f.write(f"## [STRATEGIC THEME {i+1}]\n")
            f.write(f"- **Evidence Count**: {len(items)} items\n")
            f.write("-" * 20 + "\n")
            for item in items[:20]: 
                f.write(f" - {item}\n")
            if len(items) > 20:
                f.write(f" - ... and {len(items)-20} more items.\n")
            f.write("\n")
            
    print(f"Analysis complete. Report saved to: {report_path}")

if __name__ == "__main__":
    main()
