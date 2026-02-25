Smart Document Organizer
Adaptive Epistemic Document Intelligence System (AEDIS)

A modern, open-source PySide6 desktop application for structured document analysis, entity modeling, knowledge graph construction, and multi-round adjudication workflows.

Open Source License

This project is released under the MIT License.

You are free to:

Use the software commercially

Modify the source code

Distribute copies

Create derivative works

Provided that the original copyright and license notice are included.

See the LICENSE file for full terms.

Purpose

Smart Document Organizer provides a structured analytical environment designed to:

Manage document-centric case workflows

Execute multi-round reasoning pipelines

Maintain versioned entity and relationship graphs

Attach evidence spans to structured claims

Support human-in-the-loop ACK validation

Feed curated knowledge back into iterative analytical rounds

The system emphasizes:

Provenance

Deterministic state transitions

Version-controlled knowledge

Modular service architecture

Python-only desktop runtime (no web stack)

Core Capabilities
Case Adjudication Pipeline

3-round analytical execution

Pause / resume controls

Human ACK gating between rounds

Deterministic knowledge feedback

Entity & Relationship Editor

Versioned entity records

Editable relationships

Evidence span attachment

Confidence scoring

SQLite persistence

Database Monitoring

Live SQLite health metrics

Task queue controls

API cost visibility

Structured trace inspection

Knowledge Architecture

Immutable document anchors

Mutable analytical layer

Versioned entity graph

Human-reviewed ACK records

Architecture Overview
gui/
 ├── core/
 ├── services/
 ├── tabs/
 ├── workers/
 ├── db_monitor_common.py
 ├── db_monitor_main.py

Design principles:

Separation of UI and service layers

Centralized API access

Thread-safe background workers

SQLite-backed persistence

No Node.js or web framework dependencies

This is a pure Python desktop application built with PySide6.

Installation
Requirements

Python 3.10+

PySide6

SQLite3

Requests

Setup
git clone https://github.com/your-username/smart-document-organizer.git
cd smart-document-organizer
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
python main.py
Development Guidelines

Contributors should:

Maintain Python-only architecture

Avoid introducing new runtime stacks

Preserve versioned entity + ACK semantics

Keep modules modular and decomposed

Route all external API calls through the central service layer

Large monolithic files should be refactored into services over time.

Contributing

Pull requests are welcome.

Before submitting:

Open an issue describing the change.

Keep changes modular.

Avoid architectural drift.

Maintain backward compatibility where practical.

Disclaimer

This software is provided “as is”, without warranty of any kind, express or implied, including but not limited to fitness for a particular purpose or noninfringement.

See the MIT License for full details.
