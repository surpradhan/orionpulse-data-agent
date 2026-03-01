from __future__ import annotations
"""Agent orchestration layer for OrionPulse.

This module provides deterministic and optional LLM-orchestrated answering flows,
tool execution routing, lightweight short-term memory persistence, and trace
artifact emission for debugging/operations.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analytics import anomaly_detection, forecast_metric, kpi_summary
from .llm_client import llm_chat, llm_enabled
from .memory_store import load_memory, save_memory
from .planner_contracts import validate_critique, validate_planner_plan, validate_synthesis
from .config import settings
from .db import query_df
from .specs import dashboard_spec, storyboard_spec
from .analytics_exports import export_analytics_pack
from .tool_registry import build_tool_registry
from .visualization import generate_chart, generate_insight_pack


SKILLS_DIR = Path("skills")
MEMORY_FILE = Path("data/agent_memory.json")


def _load_skills_context() -> dict[str, str]:
    """Load markdown skill files into a name->content mapping.

    Returns:
        Dictionary keyed by skill filename stem.
    """
    context: dict[str, str] = {}
    if not SKILLS_DIR.exists():
        return context
    for p in SKILLS_DIR.glob("*.md"):
        context[p.stem] = p.read_text(encoding="utf-8")
    return context


@dataclass
class AgentResponse:
    intent: str
    answer: str
    data: Any
    reasoning_summary: list[str]
    followups: list[str]
    execution_mode: str
    fallback_reason: str | None = None


class OrionAgent:
    """Lightweight orchestration layer to make behavior agentic and multi-step."""

    def __init__(self) -> None:
        self.skills = _load_skills_context()

    def _trace_enabled(self) -> bool:
        """Return whether JSON trace artifacts should be written."""
        return settings.debug_trace

    def _write_trace(self, payload: dict[str, Any]) -> None:
        """Write a timestamped trace artifact when tracing is enabled."""
        if not self._trace_enabled():
            return
        out_dir = Path(settings.trace_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (out_dir / f"trace_{ts}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _llm_enabled(self) -> bool:
        """Return True if an LLM API key is configured."""
        return llm_enabled()

    def _llm_chat(self, system_prompt: str, user_prompt: str) -> str:
        """Call the configured chat-completions endpoint and return model text."""
        return llm_chat(system_prompt, user_prompt)

    @staticmethod
    def _validate_planner_plan(data: dict[str, Any]) -> dict[str, Any]:
        """Validate planner-step JSON contract.

        Raises:
            ValueError: If required structure/types are missing or invalid.
        """
        return validate_planner_plan(data)

    @staticmethod
    def _validate_critique(data: dict[str, Any]) -> dict[str, Any]:
        """Validate critique-step JSON contract."""
        return validate_critique(data)

    @staticmethod
    def _validate_synthesis(data: dict[str, Any]) -> dict[str, Any]:
        """Validate synthesis-step JSON contract."""
        return validate_synthesis(data)

    def _parse_llm_json(self, raw: str, schema_type: str) -> dict[str, Any]:
        """Parse + repair + validate LLM JSON output with bounded retries."""
        last_error: str | None = None
        current = raw
        for attempt in range(settings.llm_json_retries + 1):
            try:
                parsed = json.loads(current)
                if not isinstance(parsed, dict):
                    raise ValueError("LLM JSON payload must be object")
                if schema_type == "planner":
                    return self._validate_planner_plan(parsed)
                if schema_type == "critique":
                    return self._validate_critique(parsed)
                if schema_type == "synthesis":
                    return self._validate_synthesis(parsed)
                raise ValueError(f"Unknown schema_type: {schema_type}")
            except Exception as exc:
                last_error = str(exc)
                if attempt >= settings.llm_json_retries:
                    break
                repair_system = (
                    "You are a JSON repair function. Return STRICT valid JSON only, no prose. "
                    "Preserve intent while fixing syntax/types to satisfy requested schema."
                )
                repair_user = json.dumps(
                    {
                        "schema_type": schema_type,
                        "bad_output": current,
                        "error": last_error,
                    },
                    ensure_ascii=False,
                )
                current = self._llm_chat(repair_system, repair_user)
        raise ValueError(f"Failed to parse/validate {schema_type} JSON after retries: {last_error}")

    def _tool_registry(self) -> dict[str, Any]:
        """Return callable registry used by LLM planner actions."""
        return build_tool_registry()

    def _rule_based_answer(self, question: str, execution_mode: str = "deterministic") -> AgentResponse:
        """Produce a deterministic answer using intent-driven routing.

        This path is used for explicit deterministic mode and as safety fallback
        when LLM orchestration is unavailable or fails.
        """
        intent = self.classify_intent(question)
        reasoning = [
            f"Classified intent as '{intent}'",
            "Retrieved relevant skills context and selected toolchain",
        ]

        if intent == "forecast":
            data = forecast_metric(settings.db_path, horizon=settings.default_forecast_horizon)
            answer = "Generated forward forecast with assumptions and recent trend context."
            followups = ["Do you want forecast split by region?", "Should I compare forecast vs last year?"]
        elif intent == "anomaly":
            data = anomaly_detection(settings.db_path)
            answer = "Detected significant outlier periods using z-score thresholding."
            followups = ["Should I explain probable drivers for each anomaly?"]
        elif intent == "dashboard":
            data = dashboard_spec()
            answer = "Created dashboard specification with KPI and trend widgets."
            followups = ["Need an operations-focused dashboard variant?"]
        elif intent == "storyboard":
            data = storyboard_spec(goal=question)
            answer = "Generated executive storyboard flow (context → insights → prediction → actions)."
            followups = ["Should I tailor this for CFO audience?"]
        elif intent == "root_cause":
            data = self._root_cause_pack()
            answer = "Prepared multi-step driver analysis pack across region, product, and anomalies."
            followups = ["Want me to convert this into action recommendations?"]
        elif intent == "kpi":
            data = kpi_summary(settings.db_path)
            answer = "Computed KPI summary across available periods."
            followups = ["Need quarter-over-quarter or YoY comparison?"]
        elif "chart" in question.lower() or "visual" in question.lower() or "graph" in question.lower():
            data = generate_insight_pack(question)
            answer = "Generated visualization insight pack with saved chart artifacts."
            followups = ["Do you want SVG exports as well?", "Should I include anomaly and forecast charts?"]
        elif "analytics export" in question.lower() or "semantic export" in question.lower() or "export pack" in question.lower():
            data = export_analytics_pack(fmt="csv")
            answer = "Generated Analytics Export pack with canonical datasets and semantic mapping files."
            followups = ["Should I also generate parquet exports?", "Need tool-specific starter templates refined further?"]
        else:
            data = {
                "message": "I can help with KPI summary, root-cause analysis, forecasts, anomalies, dashboards, and storyboards.",
                "skills_loaded": sorted(self.skills.keys()),
            }
            answer = "Mapped your request to available analytical capabilities."
            followups = ["Try: 'forecast next 3 months revenue'", "Try: 'why did margin drop in APAC?'"]

        reasoning.append("Generated structured response with next-best follow-up questions")
        return AgentResponse(
            intent=intent,
            answer=answer,
            data=data,
            reasoning_summary=reasoning,
            followups=followups,
            execution_mode=execution_mode,
        )

    def _llm_orchestrated_answer(self, question: str) -> AgentResponse:
        """Run planner/tool/critique/synthesis loop for dynamic reasoning.

        The loop is bounded by configured max steps and guarded by strict JSON
        schema validation with repair attempts.
        """
        tools = self._tool_registry()
        tool_names = sorted(tools.keys())
        observations: list[dict[str, Any]] = []
        reasoning: list[str] = []

        planner_system = (
            "You are an analytics agent planner. Return STRICT JSON only with keys: "
            "thought, action, final_answer, final, followups. "
            "If final=false, action must be {tool:string,args:object}. "
            f"Allowed tools: {tool_names}."
        )

        for step in range(1, settings.llm_max_steps + 1):
            planner_user = json.dumps(
                {
                    "question": question,
                    "step": step,
                    "skills_available": sorted(self.skills.keys()),
                    "observations": observations,
                },
                ensure_ascii=False,
            )
            raw = self._llm_chat(planner_system, planner_user)
            plan = self._parse_llm_json(raw, "planner")
            reasoning.append(str(plan.get("thought", f"Step {step} planned")))
            self._write_trace(
                {
                    "phase": "planner",
                    "step": step,
                    "question": question,
                    "plan": plan,
                    "observations_count": len(observations),
                }
            )

            if plan.get("final"):
                return AgentResponse(
                    intent="llm_dynamic",
                    answer=str(plan.get("final_answer", "Generated final response.")),
                    data={"observations": observations},
                    reasoning_summary=reasoning,
                    followups=plan.get("followups", []),
                    execution_mode="llm_orchestrated",
                )

            action = plan.get("action") or {}
            tool = action.get("tool")
            args = action.get("args") or {}
            if tool not in tools:
                observations.append({"tool": tool, "error": "Invalid tool requested by planner"})
                continue

            try:
                out = tools[tool](args)
                observations.append({"tool": tool, "args": args, "result": out})
                self._write_trace(
                    {
                        "phase": "tool_execution",
                        "step": step,
                        "tool": tool,
                        "args": args,
                        "result_preview": str(out)[:2000],
                    }
                )
            except Exception as exc:
                observations.append({"tool": tool, "args": args, "error": str(exc)})
                self._write_trace(
                    {
                        "phase": "tool_execution",
                        "step": step,
                        "tool": tool,
                        "args": args,
                        "error": str(exc),
                    }
                )

            critique_system = (
                "You are a critic. Return STRICT JSON: {continue:boolean, reason:string}. "
                "continue=false if enough evidence exists to answer confidently."
            )
            critique_user = json.dumps({"question": question, "observations": observations}, ensure_ascii=False)
            crit_raw = self._llm_chat(critique_system, critique_user)
            critique = self._parse_llm_json(crit_raw, "critique")
            reasoning.append(f"Critique: {critique.get('reason', '')}")
            self._write_trace(
                {
                    "phase": "critique",
                    "step": step,
                    "critique": critique,
                }
            )
            if critique.get("continue") is False:
                break

        synth_system = (
            "You are a business analyst agent. Return STRICT JSON with keys: "
            "answer (string), followups (array of strings)."
        )
        synth_user = json.dumps({"question": question, "observations": observations}, ensure_ascii=False)
        synth_raw = self._llm_chat(synth_system, synth_user)
        synth = self._parse_llm_json(synth_raw, "synthesis")
        self._write_trace(
            {
                "phase": "synthesis",
                "question": question,
                "synthesis": synth,
                "observations_count": len(observations),
            }
        )
        return AgentResponse(
            intent="llm_dynamic",
            answer=str(synth.get("answer", "Completed multi-hop analysis.")),
            data={"observations": observations},
            reasoning_summary=reasoning,
            followups=synth.get("followups", []),
            execution_mode="llm_orchestrated",
        )

    def classify_intent(self, question: str) -> str:
        """Classify user intent using lightweight keyword heuristics."""
        q = question.lower()
        if "forecast" in q or "predict" in q:
            return "forecast"
        if "anomaly" in q or "outlier" in q or "spike" in q:
            return "anomaly"
        if "dashboard" in q:
            return "dashboard"
        if "storyboard" in q or "narrative" in q:
            return "storyboard"
        if "root cause" in q or "why" in q or "driver" in q:
            return "root_cause"
        if "kpi" in q or "summary" in q or "performance" in q:
            return "kpi"
        return "general"

    def _root_cause_pack(self) -> dict:
        """Build a multi-source driver pack for root-cause style questions."""
        region = query_df(
            settings.db_path,
            "SELECT * FROM vw_region_performance ORDER BY net_revenue DESC LIMIT 5",
        ).to_dict(orient="records")
        product = query_df(
            settings.db_path,
            "SELECT * FROM vw_product_margin_rank ORDER BY margin_pct DESC LIMIT 5",
        ).to_dict(orient="records")
        anomalies = anomaly_detection(settings.db_path)
        return {"region_drivers": region, "product_drivers": product, "anomalies": anomalies}

    def answer(self, question: str, mode: str = "auto") -> AgentResponse:
        """Main entrypoint for agent responses.

        Args:
            question: Natural-language user query.
            mode: One of ``auto``, ``deterministic``, or ``llm``.

        Returns:
            AgentResponse with intent, answer, payload, follow-ups, and
            execution provenance metadata.
        """
        trace_session: dict[str, Any] = {
            "question": question,
            "llm_enabled": self._llm_enabled(),
            "requested_mode": mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        normalized_mode = mode.lower().strip()
        if normalized_mode not in {"auto", "deterministic", "llm"}:
            normalized_mode = "auto"

        llm_eligible = normalized_mode in {"auto", "llm"} and self._llm_enabled()

        try:
            if normalized_mode == "deterministic":
                resp = self._rule_based_answer(question, execution_mode="deterministic")
                trace_session["mode"] = "deterministic"
            elif llm_eligible:
                resp = self._llm_orchestrated_answer(question)
                trace_session["mode"] = "llm_orchestrated"
            else:
                resp = self._rule_based_answer(question, execution_mode="deterministic")
                trace_session["mode"] = "deterministic"
                if normalized_mode == "llm" and not self._llm_enabled():
                    resp.fallback_reason = "LLM mode requested but LLM is not configured"
        except Exception as exc:
            # Safety fallback to deterministic path
            resp = self._rule_based_answer(question, execution_mode="fallback_rule_based")
            resp.fallback_reason = str(exc)
            trace_session["mode"] = "fallback_rule_based"
            trace_session["fallback_reason"] = str(exc)

        mem = load_memory(MEMORY_FILE)
        mem.append({"question": question, "intent": resp.intent, "answer": resp.answer})
        save_memory(MEMORY_FILE, mem)
        trace_session["intent"] = resp.intent
        trace_session["answer"] = resp.answer
        trace_session["followups"] = resp.followups
        trace_session["execution_mode"] = resp.execution_mode
        if resp.fallback_reason:
            trace_session["fallback_reason"] = resp.fallback_reason
        self._write_trace({"phase": "final", "session": trace_session})
        return resp
