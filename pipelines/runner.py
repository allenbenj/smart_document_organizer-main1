from __future__ import annotations

import asyncio  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

from agents import get_agent_manager  # noqa: E402
from agents.orchestration.message_bus import MessageBus  # noqa: E402
from agents.utils.context_builder import AgentContextBuilder  # noqa: E402
from mem_db.knowledge import get_knowledge_manager  # noqa: E402
from mem_db.vector_store import get_vector_store  # noqa: E402


@dataclass
class Step:
    name: str
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Pipeline:
    steps: List[Step]


def _resolve_path(ctx: Dict[str, Any], path: str) -> Any:
    cur: Any = ctx
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _eval_when(expr: Any, ctx: Dict[str, Any]) -> bool:  # noqa: C901
    """Evaluate a simple boolean condition safely against ctx.

    Supported forms:
    - "a.b.c" (truthy check)
    - "not a.b"
    - "a.b and c.d" / "a.b or c.d" (left-to-right, no precedence)
    - "a.b >= 0.7" (comparators: >, <, >=, <=, ==, != against numbers)
    """
    if not expr:
        return True
    if not isinstance(expr, str):
        return bool(expr)

    def cmp(left_path: str, op: str, right_str: str) -> bool:
        left_val = _resolve_path(ctx, left_path)
        try:
            right_val = float(right_str)
        except Exception:
            right_val = right_str.strip("\"'")
        try:
            lv = float(left_val)
        except Exception:
            lv = left_val
        if op == ">=":
            return (
                isinstance(lv, (int, float))
                and isinstance(right_val, (int, float))
                and lv >= right_val
            )
        if op == "<=":
            return (
                isinstance(lv, (int, float))
                and isinstance(right_val, (int, float))
                and lv <= right_val
            )
        if op == ">":
            return (
                isinstance(lv, (int, float))
                and isinstance(right_val, (int, float))
                and lv > right_val
            )
        if op == "<":
            return (
                isinstance(lv, (int, float))
                and isinstance(right_val, (int, float))
                and lv < right_val
            )
        if op == "==":
            return lv == right_val
        if op == "!=":
            return lv != right_val
        return False

    # Very small parser: split by ' or ', then ' and '
    or_parts = [p.strip() for p in expr.split(" or ")]
    or_results: List[bool] = []
    for or_part in or_parts:
        and_parts = [p.strip() for p in or_part.split(" and ")]
        and_ok = True
        for a in and_parts:
            neg = False
            s = a
            if s.startswith("not "):
                neg = True
                s = s[4:].strip()
            # comparator?
            for op in (">=", "<=", "==", "!=", ">", "<"):
                if op in s:
                    lp, rp = s.split(op, 1)
                    val = cmp(lp.strip(), op, rp.strip())
                    break
            else:
                val = bool(_resolve_path(ctx, s))
            if neg:
                val = not val
            and_ok = and_ok and val
            if not and_ok:
                break
        or_results.append(and_ok)
    return any(or_results)


async def run_pipeline(  # noqa: C901
    pipeline: Pipeline, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ctx: Dict[str, Any] = context or {}
    manager = get_agent_manager()
    kg = get_knowledge_manager()
    vs = get_vector_store()
    bus = MessageBus()
    ctx.setdefault("messages", [])

    def should_run(step: Step) -> bool:
        cond = step.options.get("when") if step.options else None
        return _eval_when(cond, ctx)

    # Dependency-aware execution with retries/timeouts
    step_ids = [
        s.options.get("id") if s.options.get("id") else f"step_{i}"
        for i, s in enumerate(pipeline.steps)
    ]
    executed = set()
    remaining = list(range(len(pipeline.steps)))

    async def run_one(name: str, opts: Dict[str, Any]):
        if name == "process_document":
            path = opts.get("path") or ctx.get("path")
            if not path:
                raise ValueError("process_document requires 'path'")
            res = await manager.process_document(path)
            ctx.setdefault("doc", {})["processed"] = res.data
            ctx["text"] = res.data.get("content", "")
        elif name == "extract_entities":
            text = opts.get("text") or ctx.get("text") or ""
            res = await manager.extract_entities(text, **opts)
            ctx.setdefault("entities", res.data.get("entities", []))
        elif name == "semantic":
            text = opts.get("text") or ctx.get("text") or ""
            res = await manager.analyze_semantic(text, **opts)
            ctx.setdefault("semantic", res.data)
            await bus.publish(
                "semantic.topics",
                sender="semantic",
                payload={"topics": res.data.get("key_topics", [])},
            )
            ctx["messages"].append({"topic": "semantic.topics", "from": "semantic"})
        elif name == "violations":
            text = opts.get("text") or ctx.get("text") or ""
            res = await manager.analyze_violations(text, **opts)
            ctx.setdefault("violations", res.data)
        elif name == "contradictions":
            text = opts.get("text") or ctx.get("text") or ""
            res = await manager.analyze_contradictions(text, **opts)
            ctx.setdefault("contradictions", res.data)
        elif name == "classify":
            text = opts.get("text") or ctx.get("text") or ""
            res = await manager.classify_text(text, **opts)
            ctx.setdefault("classification", res.data)
        elif name == "citations":
            import re as _re  # noqa: E402

            text = opts.get("text") or ctx.get("text") or ""
            patterns = [
                _re.compile(r"\b\d+\s+U\.S\.\s+\d+\b"),
                _re.compile(r"\b\d+\s+F\.[23]d\s+\d+\b"),
                _re.compile(r"\b\d+\s+S\.Ct\.\s+\d+\b"),
            ]
            cits: List[Dict[str, Any]] = []
            for pat in patterns:
                for m in pat.finditer(text):
                    cits.append({"citation": m.group(0)})
            ctx["citations"] = cits
            await bus.publish(
                "citations.found", sender="citations", payload={"citations": cits}
            )
            ctx["messages"].append(
                {"topic": "citations.found", "from": "citations", "count": len(cits)}
            )
        elif name == "precedents":
            msgs = await bus.drain("citations.found")
            citations = ctx.get("citations") or []
            if not citations and msgs:
                for m in msgs:
                    citations = m.payload.get("citations") or []
                    break
            try:
                res = await manager.analyze_precedents(
                    [c.get("citation") for c in citations]
                )
                ctx["precedents"] = res.data
            except Exception:
                ctx["precedents"] = [
                    {"citation": c.get("citation"), "matched": False} for c in citations
                ]
        elif name == "entity_focus":
            msgs = await bus.drain("semantic.topics")
            topics: List[str] = []
            for m in msgs:
                topics.extend(
                    [
                        t.get("name") if isinstance(t, dict) else str(t)
                        for t in (m.payload.get("topics") or [])
                    ]
                )
            ctx.setdefault("focus", {})["topics"] = topics
            if topics:
                text = opts.get("text") or ctx.get("text") or ""
                res = await manager.extract_entities(text, focus_topics=topics)
                ctx.setdefault("entities", res.data.get("entities", []))
        elif name == "expert_prompt":
            builder = AgentContextBuilder()
            agent = opts.get("agent_name") or "Lex _Legal Researcher_"
            task_type = opts.get("task_type") or "legal_research_memo"
            task_data = opts.get("task_data") or (
                ctx.get("text") or "Analyze the provided legal material."
            )
            prompt = builder.generate_expert_prompt(agent, task_type, task_data)
            ctx.setdefault("expert_prompt", {})[agent] = prompt
        elif name == "embed_index":
            text = opts.get("text") or ctx.get("text") or ""
            res = await manager.embed_texts([text], **opts)
            emb = res.data.get("embeddings", [[]])[0]
            if emb and vs is not None:
                await vs.initialize()
                import numpy as np  # noqa: E402

                await vs.add_document(
                    text,
                    np.array(emb, dtype="float32"),
                    metadata=opts.get("metadata") or {},
                )
        elif name == "kg_propose":
            if kg is not None:
                ctx.setdefault("proposals", []).append(
                    {
                        "kind": opts.get("kind", "entity"),
                        "data": opts.get("data", {}),
                    }
                )
        else:
            raise ValueError(f"Unknown step: {name}")

    while remaining:
        # Collect all ready steps
        ready_indices = []
        for idx in list(remaining):
            step = pipeline.steps[idx]
            opts = step.options or {}
            if not should_run(step):
                ready_indices.append(idx)
                continue
            deps = opts.get("depends_on", [])
            if any(d not in executed for d in deps):
                continue
            ready_indices.append(idx)

        if not ready_indices:
            # No steps could run due to unsatisfied deps; stop to avoid deadlock
            break

        # Run ready steps in parallel
        tasks = []
        meta = []
        for idx in ready_indices:
            step = pipeline.steps[idx]
            sid = step_ids[idx]
            name = step.name
            opts = step.options or {}

            async def _runner(n=name, o=opts, s_id=sid):
                try:
                    retries = int(o.get("retries", 0))
                    timeout = o.get("timeout")
                    delay = float(o.get("retry_delay", 0.5))
                    attempt = 0
                    while True:
                        try:
                            coro = run_one(n, o)
                            if timeout:
                                await asyncio.wait_for(coro, timeout=float(timeout))
                            else:
                                await coro
                            break
                        except Exception as e:  # noqa: F841
                            if attempt >= retries:
                                raise
                            attempt += 1
                            await asyncio.sleep(delay)
                    return (s_id, None)
                except Exception as e:
                    return (s_id, str(e))

            tasks.append(asyncio.create_task(_runner()))
            meta.append((idx, sid))

        results = await asyncio.gather(*tasks)
        # Mark executed and record errors
        for (sid, err), (idx, _sid) in zip(results, meta):
            executed.add(sid)
            if err:
                ctx.setdefault("errors", []).append(
                    {"step": pipeline.steps[idx].name, "id": sid, "error": err}
                )
            remaining.remove(idx)

    return ctx
