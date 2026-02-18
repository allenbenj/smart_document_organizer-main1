"""Task execution and analysis operations for ProductionAgentManager."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.core.models import AgentResult, AgentType


class OperationsMixin:
    async def process_document(self, file_path: str, **kwargs) -> AgentResult:
        """Process a document using the Document Processor agent."""
        start_time = datetime.now()

        try:
            if not self.is_initialized:
                return AgentResult(
                    success=False,
                    data={},
                    error="Production system not initialized",
                    agent_type="document_processor",
                )

            agent = self.agents.get(AgentType.DOCUMENT_PROCESSOR)
            if not agent:
                return AgentResult(
                    success=False,
                    data={},
                    error="Document processor not available",
                )
            result = await agent._process_task(task_data=file_path, metadata=kwargs)

            processing_time = (datetime.now() - start_time).total_seconds()

            if not isinstance(result, dict):
                return AgentResult(
                    success=False,
                    data={},
                    error="document_processor returned invalid result",
                    processing_time=processing_time,
                    agent_type="document_processor",
                )

            ok = bool(result.get("success", False))
            err = result.get("error")
            if not ok and not err:
                err = "document processing failed"

            return AgentResult(
                success=ok,
                data=result,
                error=err,
                processing_time=processing_time,
                agent_type="document_processor",
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Document processing failed: {e}")
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=processing_time,
                agent_type="document_processor",
            )

    async def extract_entities(self, text: str, **kwargs) -> AgentResult:
        """Extract entities using the Legal Entity Extractor agent."""
        start_time = datetime.now()

        try:
            if not self.is_initialized:
                processing_time = (datetime.now() - start_time).total_seconds()
                from config.extraction_patterns import extract_entities_from_text  # noqa: E402

                entities = extract_entities_from_text(text)
                return AgentResult(
                    success=True,
                    data={"entities": entities},
                    processing_time=processing_time,
                    agent_type="entity_extractor",
                )

            agent = self.agents.get(AgentType.ENTITY_EXTRACTOR)
            if not agent:
                from agents.utils.context_builder import (  # noqa: E402
                    build_degradation_notice,
                )

                return AgentResult(
                    success=False,
                    data={},
                    error="Entity extractor not available",
                    agent_type="entity_extractor",
                    metadata={
                        "degradation": build_degradation_notice(
                            component="entity_extractor",
                            lost_features=[
                                "hybrid legal NER",
                                "legal-type validation & deduplication",
                                "KG integration & shared memory persistence",
                            ],
                            reason="production agent missing",
                            suggested_actions=[
                                "Enable AGENTS_ENABLE_ENTITY_EXTRACTOR",
                                "Install required NLP models",
                                "Verify agent registry initialization",
                            ],
                        )
                    },
                )

            result = await agent._process_task(task_data=text, metadata=kwargs)

            processing_time = (datetime.now() - start_time).total_seconds()

            if not isinstance(result, dict):
                result = {"success": False, "entities": []}

            if not result.get("success", False):
                # Resilient fallback so GUI still works when advanced NER models are missing
                import re

                ents = []
                for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text):
                    ents.append(
                        {"text": m.group(0), "label": "PROPER_NOUN", "confidence": 0.55}
                    )
                for m in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", text):
                    ents.append(
                        {"text": m.group(0), "label": "DATE", "confidence": 0.7}
                    )
                return AgentResult(
                    success=True,
                    data={"entities": ents, "fallback": True},
                    processing_time=processing_time,
                    agent_type="entity_extractor",
                    metadata={"mode": "fallback-regex"},
                )

            return AgentResult(
                success=True,
                data=result,
                processing_time=processing_time,
                agent_type="entity_extractor",
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Entity extraction failed: {e}")
            # Last-resort fallback to keep UI functional
            import re

            ents = []
            for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text):
                ents.append(
                    {"text": m.group(0), "label": "PROPER_NOUN", "confidence": 0.5}
                )
            return AgentResult(
                success=True,
                data={"entities": ents, "fallback": True, "source_error": str(e)},
                processing_time=processing_time,
                agent_type="entity_extractor",
                metadata={"mode": "fallback-regex"},
            )

    async def classify_text(self, text: str, **kwargs) -> AgentResult:  # noqa: C901
        """Classify text using transformers zero-shot if available, with fallback keywords."""
        start_time = datetime.now()
        try:
            labels = kwargs.get("labels") or [
                "contract",
                "court_filing",
                "statute",
                "compliance_risk",
                "general_document",
            ]

            import os

            model_name = (
                kwargs.get("model_name")
                or os.getenv("AGENTS_ZS_CLASSIFIER_MODEL")
                or "typeform/distilbert-base-uncased-mnli"
            )
            quality_gate = bool(kwargs.get("quality_gate"))

            try:
                import torch  # type: ignore  # noqa: E402
                from transformers import pipeline  # type: ignore  # noqa: E402

                device = 0 if torch.cuda.is_available() else -1
                zsc = pipeline(
                    "zero-shot-classification",
                    model=model_name,
                    device=device,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else None,
                )
                result = zsc(text, labels)
                best_label = result["labels"][0]
                best_score = float(result["scores"][0])
                data = {
                    "labels": [
                        {"label": l, "confidence": float(s)}
                        for l, s in zip(result["labels"], result["scores"])
                    ],
                    "primary": {"label": best_label, "confidence": best_score},
                    "used_ml_model": True,
                }
                if quality_gate:
                    data["labels"] = [
                        x for x in data["labels"] if x["confidence"] >= 0.7
                    ]
                    if not data["labels"]:
                        data["labels"] = [
                            {"label": "low_confidence", "confidence": 0.5}
                        ]
                return AgentResult(
                    success=True,
                    data=data,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_type="classifier",
                )
            except Exception:
                lower = text.lower()
                labels_out = []
                if any(k in lower for k in ["contract", "agreement", "terms"]):
                    labels_out.append({"label": "contract", "confidence": 0.82})
                if any(k in lower for k in ["motion", "order", "brie"]):
                    labels_out.append({"label": "court_filing", "confidence": 0.76})
                if any(k in lower for k in ["illegal", "violation", "breach"]):
                    labels_out.append({"label": "compliance_risk", "confidence": 0.74})
                if not labels_out:
                    labels_out.append({"label": "general_document", "confidence": 0.6})
                if quality_gate:
                    labels_out = [
                        l for l in labels_out if l.get("confidence", 0) >= 0.7
                    ]
                    if not labels_out:
                        labels_out = [{"label": "low_confidence", "confidence": 0.5}]
                return AgentResult(
                    success=True,
                    data={"labels": labels_out, "used_ml_model": False},
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_type="classifier",
                )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="classifier",
            )

    async def embed_texts(self, texts: list[str], **kwargs) -> AgentResult:
        """Compute embeddings using sentence-transformers if available."""
        start_time = datetime.now()
        try:
            import os

            model_name = (
                kwargs.get("model")
                or os.getenv("AGENTS_EMBED_MODEL")
                or "sentence-transformers/all-MiniLM-L6-v2"
            )
            try:
                import torch  # type: ignore  # noqa: E402
                from sentence_transformers import SentenceTransformer  # type: ignore  # noqa: E402

                device = "cuda" if torch.cuda.is_available() else "cpu"
                model = SentenceTransformer(model_name, device=device)
                embs = model.encode(
                    texts, convert_to_numpy=True, normalize_embeddings=True
                )
                data = {"embeddings": [vec.astype(float).tolist() for vec in embs]}
                return AgentResult(
                    success=True,
                    data=data,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_type="embedder",
                    metadata={"mode": "sentence-transformers", "model": model_name},
                )
            except Exception:
                import hashlib
                import math

                out = []
                for t in texts:
                    h = hashlib.sha256(t.encode("utf-8")).digest()
                    vec = [(h[i] / 255.0) for i in range(32)]
                    vec += vec
                    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
                    vec = [v / norm for v in vec]
                    out.append(vec)
                return AgentResult(
                    success=True,
                    data={"embeddings": out},
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_type="embedder",
                    metadata={"mode": "fallback", "dim": 64},
                )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="embedder",
            )

    async def analyze_legal_reasoning(
        self, document_content: str, **kwargs
    ) -> AgentResult:  # noqa: C901
        """Analyze legal reasoning using the Legal Reasoning Engine."""
        start_time = datetime.now()

        try:
            if not self._flags.get("AGENTS_ENABLE_LEGAL_REASONING", True):
                return AgentResult(
                    success=False,
                    data={},
                    error="legal_reasoning disabled by flag",
                    processing_time=0.0,
                    agent_type="legal_reasoning",
                )
            if not self.is_initialized:
                return AgentResult(
                    success=False,
                    data={},
                    error="Production system not initialized",
                    agent_type="legal_reasoning",
                )

            agent = self.agents.get(AgentType.LEGAL_REASONING)
            if not agent:
                return AgentResult(
                    success=False,
                    data={},
                    error="Legal reasoning engine not available",
                    agent_type="legal_reasoning",
                )

            analysis_type = kwargs.get("analysis_type", "comprehensive")
            key_src = f"{document_content}\n|{analysis_type}"
            import hashlib as _hashlib

            key = _hashlib.sha1(key_src.encode("utf-8")).hexdigest()

            now = datetime.now()
            cached = self._cache.get(key)
            if cached and (now - cached[0]) <= self._cache_ttl:
                data = dict(cached[1])
                data.setdefault("metadata", {})["cache_hit"] = True
                return AgentResult(
                    success=True,
                    data=data,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_type="legal_reasoning",
                    metadata={"mode": "production", "cache": "hit"},
                )

            timeout = float(kwargs.get("timeout", self._default_timeout))

            async def _compute() -> Dict[str, Any]:
                document_id = kwargs.get("document_id", f"doc_{hash(document_content)}")
                try:
                    import hashlib as _h

                    from agents.utils.prompt_engineering import (
                        build_legal_reasoning_prompt,
                    )

                    _th = _h.sha1(document_content.encode("utf-8")).hexdigest()
                    prompt_meta = build_legal_reasoning_prompt(
                        _th, analysis_type=analysis_type
                    )
                except Exception:
                    prompt_meta = {"meta": {"analysis_type": analysis_type}}
                result = await agent.analyze_legal_document(
                    document_content=document_content,
                    document_id=document_id,
                    analysis_type=analysis_type,
                )
                out = result.to_dict() if hasattr(result, "to_dict") else dict(result)

                lower = document_content.lower()
                signals = []
                for s, lbl in [
                    ("breach", "contract_breach"),
                    ("illegal", "legal_compliance"),
                    ("non-payment", "payment_terms"),
                ]:
                    if s in lower:
                        signals.append({"signal": s, "label": lbl, "confidence": 0.7})
                reasoning_trace = [
                    {
                        "step": "ingest",
                        "evidence": f"len={len(document_content)} chars",
                        "score": 1.0,
                    },
                    {
                        "step": "keyword_scan",
                        "evidence": ", ".join(x["signal"] for x in signals) or "none",
                        "score": 0.6,
                    },
                ]
                triples = []
                for w in [
                    "breach",
                    "violate",
                    "violates",
                    "contradict",
                    "prohibit",
                    "allow",
                ]:
                    if w in lower:
                        triples.append(["contract", w, "obligation"])
                out.setdefault("knowledge_graph", {"triples": triples})
                out.setdefault("matched_signals", signals)
                out.setdefault("reasoning_trace", reasoning_trace)
                out.setdefault("metadata", {})
                out["metadata"].update(
                    {"timeout": timeout, "cache_hit": False, "prompt": prompt_meta}
                )
                return out

            try:
                final = await asyncio.wait_for(_compute(), timeout=timeout)
            except asyncio.TimeoutError:
                final = {
                    "analysis_type": analysis_type,
                    "legal_issues": [],
                    "legal_arguments": [],
                    "compliance_checks": [],
                    "knowledge_graph": {"triples": []},
                    "reasoning_trace": [
                        {
                            "step": "timeout",
                            "evidence": "analysis exceeded timeout",
                            "score": 0.0,
                        }
                    ],
                    "issue": "Timed out",
                    "confidence": 0.0,
                    "overall_confidence": 0.0,
                    "processing_method": "timeout_production",
                    "metadata": {"timed_out": True},
                }

            final.setdefault("metadata", {})
            import hashlib as _hid

            final.setdefault(
                "analysis_id",
                _hid.sha1(
                    (document_content + "|" + analysis_type).encode("utf-8")
                ).hexdigest(),
            )

            self._cache[key] = (datetime.now(), final)

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                success=True,
                data=final,
                processing_time=processing_time,
                agent_type="legal_reasoning",
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Legal reasoning analysis failed: {e}")
            lower = (document_content or "").lower()
            issues = []
            if "breach" in lower:
                issues.append({"issue": "possible breach", "confidence": 0.65})
            if "illegal" in lower or "violation" in lower:
                issues.append(
                    {"issue": "possible compliance violation", "confidence": 0.65}
                )
            return AgentResult(
                success=True,
                data={
                    "analysis_type": kwargs.get("analysis_type", "comprehensive"),
                    "legal_issues": issues,
                    "reasoning_trace": [
                        {"step": "fallback", "evidence": str(e), "score": 0.4}
                    ],
                    "metadata": {"mode": "fallback-heuristic", "source_error": str(e)},
                },
                processing_time=processing_time,
                agent_type="legal_reasoning",
                metadata={"mode": "fallback-heuristic"},
            )

    async def submit_feedback(
        self,
        analysis_id: str,
        agent: str,
        rating: int,
        comments: Optional[str] = None,
        tags: Optional[List[str]] = None,
        suggested_corrections: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist feedback to jsonl; hook for future adaptive tuning."""
        try:
            payload = {
                "analysis_id": analysis_id,
                "agent": agent,
                "rating": int(rating),
                "comments": comments or "",
                "tags": tags or [],
                "suggested_corrections": suggested_corrections or {},
                "timestamp": datetime.now().isoformat(),
                "source": "production",
            }
            self._feedback_path.parent.mkdir(parents=True, exist_ok=True)
            with self._feedback_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
            return {"stored": True, "path": str(self._feedback_path)}
        except Exception as e:
            self.logger.error(f"Failed to store feedback: {e}")
            return {"stored": False, "error": str(e)}

    async def analyze_irac(self, document_text: str, **kwargs) -> AgentResult:
        """Analyze document using IRAC framework."""
        start_time = datetime.now()

        try:
            if not self._flags.get("AGENTS_ENABLE_IRAC", True):
                return AgentResult(
                    success=False,
                    data={},
                    error="irac disabled by flag",
                    processing_time=0.0,
                    agent_type="irac_analyzer",
                )
            if not self.is_initialized:
                processing_time = (datetime.now() - start_time).total_seconds()
                return AgentResult(
                    success=True,
                    data={"text": document_text, "irac_stub": True},
                    processing_time=processing_time,
                    agent_type="irac_analyzer",
                )

            agent = self.agents.get(AgentType.IRAC_ANALYZER)
            if not agent:
                return AgentResult(
                    success=False,
                    data={},
                    error="IRAC analyzer not available",
                    agent_type="irac_analyzer",
                )

            result = await agent._process_task(task_data=document_text, metadata=kwargs)

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                success=result.get("success", False),
                data=result,
                processing_time=processing_time,
                agent_type="irac_analyzer",
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"IRAC analysis failed: {e}")
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=processing_time,
                agent_type="irac_analyzer",
            )

    async def analyze_toulmin(self, document_content: str, **kwargs) -> AgentResult:
        """Analyze document using Toulmin model."""
        start_time = datetime.now()

        try:
            if not self._flags.get("AGENTS_ENABLE_TOULMIN", True):
                return AgentResult(
                    success=False,
                    data={},
                    error="toulmin disabled by flag",
                    processing_time=0.0,
                    agent_type="toulmin_analyzer",
                )
            if not self.is_initialized:
                processing_time = (datetime.now() - start_time).total_seconds()
                return AgentResult(
                    success=True,
                    data={"text": document_content, "toulmin_stub": True},
                    processing_time=processing_time,
                    agent_type="toulmin_analyzer",
                )

            agent = self.agents.get(AgentType.TOULMIN_ANALYZER)
            if not agent:
                return AgentResult(
                    success=False,
                    data={},
                    error="Toulmin analyzer not available",
                    agent_type="toulmin_analyzer",
                )

            result = await agent.analyze_async(
                document_content=document_content, context=kwargs
            )

            processing_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                success=not result.get("error"),
                data=result,
                processing_time=processing_time,
                agent_type="toulmin_analyzer",
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Toulmin analysis failed: {e}")
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=processing_time,
                agent_type="toulmin_analyzer",
            )

    async def analyze_precedents(self, citations: List[str], **kwargs) -> AgentResult:
        """Analyze citations and find precedents (if analyzer available)."""
        start_time = datetime.now()
        try:
            if not self.is_initialized:
                return AgentResult(
                    success=False,
                    data={},
                    error="Production system not initialized",
                    agent_type="precedent_analyzer",
                )
            if self._precedent_analyzer is None:
                return AgentResult(
                    success=True,
                    data={
                        "matches": [
                            {"citation": c, "matched": False} for c in citations
                        ]
                    },
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_type="precedent_analyzer",
                )
            try:
                if hasattr(self._precedent_analyzer, "analyze_citations"):
                    result = await self._precedent_analyzer.analyze_citations(
                        citations, **kwargs
                    )
                elif hasattr(self._precedent_analyzer, "match_citations"):
                    result = await self._precedent_analyzer.match_citations(
                        citations, **kwargs
                    )
                elif hasattr(self._precedent_analyzer, "analyze"):
                    result = await self._precedent_analyzer.analyze(
                        {"citations": citations, **kwargs}
                    )
                else:
                    result = await self._precedent_analyzer._process_task(
                        {"citations": citations}, kwargs
                    )
                return AgentResult(
                    success=True,
                    data=result,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_type="precedent_analyzer",
                )
            except Exception as e:
                # Graceful fallback: echo citations as unresolved matches so pipeline continues.
                return AgentResult(
                    success=True,
                    data={
                        "matches": [
                            {"citation": c, "matched": False, "reason": str(e)}
                            for c in citations
                        ],
                        "fallback": True,
                    },
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_type="precedent_analyzer",
                    metadata={"mode": "fallback"},
                )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="precedent_analyzer",
            )

    async def analyze_semantic(self, text: str, **kwargs) -> AgentResult:
        """Semantic analysis (advanced only, no heuristics)."""
        start_time = datetime.now()
        try:
            if not self.is_initialized or not self._flags.get(
                "AGENTS_ENABLE_SEMANTIC", True
            ):
                from agents.utils.context_builder import build_degradation_notice

                return AgentResult(
                    success=False,
                    data={},
                    error="semantic analyzer unavailable",
                    processing_time=0.0,
                    agent_type="semantic_analyzer",
                    metadata={
                        "degradation": build_degradation_notice(
                            component="semantic_analyzer",
                            lost_features=[
                                "advanced semantic summarization",
                                "topic and key phrase extraction",
                                "pipeline collaboration (topic bus)",
                            ],
                            reason="production agent missing",
                            suggested_actions=[
                                "Enable AGENTS_ENABLE_SEMANTIC",
                                "Ensure model weights installed",
                                "Verify agent registry initialization",
                            ],
                        )
                    },
                )
            agent = (
                self.agents.get(AgentType.SEMANTIC_ANALYZER)
                if hasattr(AgentType, "SEMANTIC_ANALYZER")
                else None
            )
            if not agent:
                from agents.utils.context_builder import build_degradation_notice

                return AgentResult(
                    success=False,
                    data={},
                    error="semantic analyzer not available",
                    processing_time=0.0,
                    agent_type="semantic_analyzer",
                    metadata={
                        "degradation": build_degradation_notice(
                            component="semantic_analyzer",
                            lost_features=[
                                "advanced semantic summarization",
                                "topic and key phrase extraction",
                                "pipeline collaboration (topic bus)",
                            ],
                            reason="production agent missing",
                            suggested_actions=[
                                "Enable AGENTS_ENABLE_SEMANTIC",
                                "Ensure model weights installed",
                                "Verify agent registry initialization",
                            ],
                        )
                    },
                )
            result = await agent._process_task(task_data=text, metadata=kwargs)
            return AgentResult(
                success=result.get("success", bool(result)),
                data=result,
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="semantic_analyzer",
            )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="semantic_analyzer",
            )

    async def analyze_contradictions(self, text: str, **kwargs) -> AgentResult:
        """Heuristic contradiction detection."""
        start_time = datetime.now()
        try:
            lower = text.lower()
            flags = []
            keywords = [
                ("not", "shall"),
                ("prohibited", "allowed"),
                ("must", "may not"),
                ("forbidden", "permitted"),
            ]
            for a, b in keywords:
                if a in lower and b in lower:
                    flags.append({"pattern": f"{a} & {b}", "confidence": 0.6})
            return AgentResult(
                success=True,
                data={"contradictions": flags},
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="contradiction_detector",
                metadata={"mode": "heuristic"},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="contradiction_detector",
            )

    async def analyze_violations(self, text: str, **kwargs) -> AgentResult:
        """Heuristic violation review with simple keyword signals."""
        start_time = datetime.now()
        try:
            issues = []
            for kw, rule in [
                ("illegal", "legal_compliance"),
                ("non-payment", "payment_terms"),
                ("breach", "contract_compliance"),
            ]:
                if kw in text.lower():
                    issues.append(
                        {
                            "issue": kw,
                            "rule": rule,
                            "severity": "medium",
                            "confidence": 0.7,
                        }
                    )
            return AgentResult(
                success=True,
                data={"violations": issues},
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="violation_review",
                metadata={"mode": "heuristic"},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="violation_review",
            )

    async def analyze_contract(self, text: str, **kwargs) -> AgentResult:
        """Analyze contract text using ContractAnalyzer (lazy init)."""
        start_time = datetime.now()
        try:
            if not self.is_initialized:
                return AgentResult(
                    success=False,
                    data={},
                    error="Production system not initialized",
                    agent_type="contract_analyzer",
                )

            if self._contract_analyzer is None:
                from agents.legal.contract_analyzer import create_contract_analyzer

                self._contract_analyzer = await create_contract_analyzer(
                    self.service_container
                )

            result = await self._contract_analyzer._process_task(text, kwargs or {})
            if not isinstance(result, dict):
                result = {"sections": [], "confidence": 0.0}

            return AgentResult(
                success=True,
                data=result,
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="contract_analyzer",
            )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="contract_analyzer",
            )

    async def check_compliance(self, text: str, **kwargs) -> AgentResult:
        """Check compliance using ComplianceChecker (lazy init)."""
        start_time = datetime.now()
        try:
            if not self.is_initialized:
                return AgentResult(
                    success=False,
                    data={},
                    error="Production system not initialized",
                    agent_type="compliance_checker",
                )

            if self._compliance_checker is None:
                from agents.legal.compliance_checker import create_compliance_checker

                self._compliance_checker = await create_compliance_checker(
                    self.service_container
                )

            result = await self._compliance_checker._process_task(text, kwargs or {})
            if not isinstance(result, dict):
                result = {
                    "status": "UNCLEAR",
                    "violations": [],
                    "recommendations": [],
                    "confidence": 0.0,
                }

            return AgentResult(
                success=True,
                data=result,
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="compliance_checker",
            )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="compliance_checker",
            )

    async def orchestrate(self, text: str, **kwargs) -> AgentResult:
        """Run a DAG pipeline: entities + semantic (parallel) → violations."""
        start_time = datetime.now()
        try:
            from agents.analysis.dag_orchestrator import DagOrchestrator

            orchestrator = DagOrchestrator(self)
            data = await orchestrator.run(text, kwargs)
            return AgentResult(
                success=True,
                data=data,
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="orchestrator",
                metadata={"mode": "dag"},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
                agent_type="orchestrator",
            )
