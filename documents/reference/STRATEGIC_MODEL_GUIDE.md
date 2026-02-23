# AEDIS Intelligence Layer: Strategic Model Guide

This document outlines the local high-fidelity models integrated into the Adaptive Epistemic Document Intelligence System (AEDIS). Use this guide to determine which model to deploy for specific legal discovery tasks.

---

## 🛰️ 1. Relationship Finder (Relation Extraction)
**Model Asset:** `models/rebel-relation`  
**Logic Type:** Sequence-to-Sequence Triple Extraction (Subject -> Relation -> Object)

### 🎯 Strategic Use Case:
Use this to auto-populate the **Knowledge Graph**. While NER tells you who is in the document, this model tells you **how they are connected**.
*   **Example**: Identifying that "Officer Smith" *arrested* "John Doe" or "Attorney Jones" *represents* "Defendant X."

### 🚀 When to Run:
*   **Trigger**: Immediately after **Entity Extraction**.
*   **Workflow**: Once you have your "Characters" (Entities), run this to find the "Plot" (Relationships) between them.

---

## ⚖️ 2. Evidence Verifier (Natural Language Inference - NLI)
**Model Asset:** `models/nli-verifier`  
**Logic Type:** Cross-Encoder (Premise + Hypothesis -> Support/Contradict/Neutral)

### 🎯 Strategic Use Case:
The "Truth Gate." Use this for the **Judge (Phase 4)** logic to verify if raw evidence actually supports a legal claim.
*   **Example**: **Claim**: "The ADA committed a discovery violation." **Evidence**: "The ADA delayed production of medical records for 4 years." **NLI Result**: `SUPPORTS` (98% confidence).

### 🚀 When to Run:
*   **Trigger**: During **Legal Reasoning** or **Audit** phases.
*   **Workflow**: Use this to filter out "weak" evidence and only keep the "Smoking Gun" facts.

---

## 📜 3. Legal Context Specialist (Legal-BERT)
**Model Asset:** `models/legal-bert`  
**Logic Type:** Domain-Specific Transformer (Trained on Court Filings/Contracts)

### 🎯 Strategic Use Case:
High-precision understanding of "Legalese." General models (like standard BERT) see the word "Motion" and think of movement; Legal-BERT knows it’s a formal request to a judge.
*   **Use for**: Precise classification of complex legal terms and statutory citations.

### 🚀 When to Run:
*   **Trigger**: During **Initial Classification** of new documents.
*   **Workflow**: Use this as the "First Responder" to determine if a document is a Motion, an Order, or a Transcript.

---

## 📖 4. Long-Context Summarizer (Longformer/LED)
**Model Asset:** `models/long-summarizer`  
**Logic Type:** Long-Range Attention (Supports 16,000+ tokens)

### 🎯 Strategic Use Case:
Condensing massive case files (50+ pages) without losing critical details hidden in the middle. Standard summarizers only "read" the first 2 pages.
*   **Example**: Summarizing an entire 300-page deposition transcript into a 5-page **Strategic Brief**.

### 🚀 When to Run:
*   **Trigger**: When a document exceeds **5,000 characters**.
*   **Workflow**: Use this to generate the "Executive Overview" before diving into deeper clustering or extraction.

---

## 🧩 5. Semantic Anchor (all-MiniLM / Nomic)
**Model Asset:** `models/all-minilm-L6-v2` | `models/nomic-embed-text`  
**Logic Type:** Vector Embedding & Clustering

### 🎯 Strategic Use Case:
The "Compass" for **Strategic Clustering**. Groups similar ideas together to find patterns of misconduct or theory.
*   **Example**: Finding all sentences across 10 documents that discuss "unlawful search and seizure" even if they use different words.

### 🚀 When to Run:
*   **Trigger**: On every document during **Ingestion**.
*   **Workflow**: Always run this first to get the "Map" of the document's themes.

---

---

## 🛠️ 6. Multi-Task Zero-Shot Oracle (GLiNER-Multi)
**Model Asset:** `models/gliner_zero_shot`  
**Logic Type:** Multi-Task Universal Extraction

### 🎯 Strategic Use Case:
The "Swiss Army Knife" of AEDIS. This single model replaces the need for multiple specialized pipelines for exploratory work.
*   **NER**: Zero-shot discovery of any label you type.
*   **Relation Extraction**: Identifies connections without pre-defined schemas.
*   **Question-Answering**: Directly query the text (e.g., "What was the date of the search warrant?").
*   **Open IE**: Extract user-defined patterns like "Product Descriptions" or "Police Badge Numbers."
*   **Sentiment/Key-Phrases**: Rapid thematic tagging.

### 🚀 When to Run:
*   **Trigger**: Use when the **Robust Ontology** doesn't have a specific label for what you're looking for.
*   **Workflow**: The "Explorer" mode. Run this to find things you didn't know you were looking for.
*   **Model Loading**: Always prefer `local_files_only=True` to ensure air-gapped performance.
*   **Ensemble Strategy**: For critical entities (Witnesses/Dates), run **BART** and **GLiNER** simultaneously and use the **Judge** to resolve disagreements.

**AEDIS Status**: All Intelligence Layers are now structured for High-Fidelity local execution.
