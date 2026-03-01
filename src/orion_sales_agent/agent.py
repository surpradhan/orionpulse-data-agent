from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .analytics import anomaly_detection, forecast_metric, kpi_summary
from .config import settings
from .db import query_df
from .specs import dashboard_spec, storyboard_spec
from .bi_exports import export_bi_pack
from .visualization import generate_chart, generate_insight_pack


SKILLS_DIR = Path("skills")
MEMORY_FILE = Path("data/agent_memory.json")


def _load_skills_context() -> dict[str, str]:
    context: dict[str, str] = {}
    if not SKILLS_DIR.exists():
        return context
    for p in SKILLS_DIR.glob("*.md"):
        context[p.stem] = p.read_text(encoding="utf-8")
    return context


def _load_memory() -> list[dict[str, Any]]:
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_memory(items: list[dict[str, Any]]) -> None:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(items[-20:], indent=2), encoding="utf-8")


@dataclass
class AgentResponse:
    intent: str
    answer: str
    data: Any
    reasoning_summary: list[str]
    followups: list[str]


class OrionAgent:
    """Lightweight orchestration layer to make behavior agentic and multi-step."""

    def __init__(self) -> None:
        self.skills = _load_skills_context()

    def _trace_enabled(self) -> bool:
        return settings.debug_trace

    def _write_trace(self, payload: dict[str, Any]) -> None:
        if not self._trace_enabled():
            return
        out_dir = Path(settings.trace_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (out_dir / f"trace_{ts}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _llm_enabled(self) -> bool:
        return bool(settings.llm_api_key.strip())

    def _llm_chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self._llm_enabled():
            raise RuntimeError("LLM not configured")

        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.llm_model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=30) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _validate_planner_plan(data: dict[str, Any]) -> dict[str, Any]:
        required = {"thought", "final"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Planner JSON missing keys: {sorted(missing)}")
        if not isinstance(data.get("final"), bool):
            raise ValueError("Planner 'final' must be boolean")
        if data.get("final"):
            if not isinstance(data.get("final_answer", ""), str):
                raise ValueError("Planner final_answer must be string when final=true")
        else:
            action = data.get("action")
            if not isinstance(action, dict):
                raise ValueError("Planner action must be object when final=false")
            if not isinstance(action.get("tool"), str):
                raise ValueError("Planner action.tool must be string")
            if not isinstance(action.get("args", {}), dict):
                raise ValueError("Planner action.args must be object")
        if "followups" in data and not isinstance(data.get("followups"), list):
            raise ValueError("Planner followups must be array")
        return data

    @staticmethod
    def _validate_critique(data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data.get("continue"), bool):
            raise ValueError("Critique 'continue' must be boolean")
        if not isinstance(data.get("reason", ""), str):
            raise ValueError("Critique 'reason' must be string")
        return data

    @staticmethod
    def _validate_synthesis(data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data.get("answer", ""), str):
            raise ValueError("Synthesis 'answer' must be string")
        if "followups" in data and not isinstance(data.get("followups"), list):
            raise ValueError("Synthesis 'followups' must be array")
        return data

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
        return {
            "kpi_summary": lambda args: kpi_summary(
                settings.db_path,
                grain=str(args.get("grain", settings.default_grain)),
                period_filter=args.get("period_filter"),
            ),
            "forecast": lambda args: forecast_metric(
                settings.db_path,
                metric=str(args.get("metric", "net_revenue")),
                horizon=int(args.get("horizon", settings.default_forecast_horizon)),
            ),
            "anomaly": lambda args: anomaly_detection(
                settings.db_path,
                metric=str(args.get("metric", "net_revenue")),
                threshold=float(args.get("threshold", 2.0)),
            ),
            "dashboard": lambda args: dashboard_spec(
                template_name=str(args.get("template_name", "exec_overview")),
                filters=args.get("filters") if isinstance(args.get("filters"), dict) else None,
            ),
            "storyboard": lambda args: storyboard_spec(
                goal=str(args.get("goal", "Executive review")),
                audience=str(args.get("audience", "exec")),
                period=str(args.get("period", "latest_quarter")),
            ),
            "top_regions": lambda args: query_df(
                settings.db_path,
                "SELECT * FROM vw_region_performance ORDER BY net_revenue DESC LIMIT 5",
            ).to_dict(orient="records"),
            "top_products": lambda args: query_df(
                settings.db_path,
                "SELECT * FROM vw_product_margin_rank ORDER BY margin_pct DESC LIMIT 5",
            ).to_dict(orient="records"),
            "generate_chart": lambda args: generate_chart(
                chart_type=str(args.get("chart_type", "kpi_trend")),
                metric=str(args.get("metric", "net_revenue")),
                horizon=int(args.get("horizon", settings.default_forecast_horizon)),
                threshold=float(args.get("threshold", 2.0)),
                fmt=str(args.get("fmt", "png")),
            ),
            "generate_insight_pack": lambda args: generate_insight_pack(
                question=str(args.get("question", "")),
                fmt=str(args.get("fmt", "png")),
            ),
            "export_bi_pack": lambda args: export_bi_pack(fmt=str(args.get("fmt", "csv"))),
        }

    def _rule_based_answer(self, question: str) -> AgentResponse:
        """Fallback path when no LLM key is configured."""
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
        elif "power bi" in question.lower() or "tableau" in question.lower() or "oracle analytics" in question.lower() or "bi export" in question.lower():
            data = export_bi_pack(fmt="csv")
            answer = "Generated BI export pack with canonical datasets and semantic mapping files."
            followups = ["Should I also generate parquet exports?", "Need tool-specific starter templates refined further?"]
        else:
            data = {
                "message": "I can help with KPI summary, root-cause analysis, forecasts, anomalies, dashboards, and storyboards.",
                "skills_loaded": sorted(self.skills.keys()),
            }
            answer = "Mapped your request to available analytical capabilities."
            followups = ["Try: 'forecast next 3 months revenue'", "Try: 'why did margin drop in APAC?'"]

        reasoning.append("Generated structured response with next-best follow-up questions")
        return AgentResponse(intent=intent, answer=answer, data=data, reasoning_summary=reasoning, followups=followups)

    def _llm_orchestrated_answer(self, question: str) -> AgentResponse:
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
        )

    def classify_intent(self, question: str) -> str:
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

    def answer(self, question: str) -> AgentResponse:
        trace_session: dict[str, Any] = {
            "question": question,
            "llm_enabled": self._llm_enabled(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            resp = self._llm_orchestrated_answer(question) if self._llm_enabled() else self._rule_based_answer(question)
            trace_session["mode"] = "llm_orchestrated" if self._llm_enabled() else "rule_based"
        except Exception as exc:
            # Safety fallback to deterministic path
            resp = self._rule_based_answer(question)
            trace_session["mode"] = "fallback_rule_based"
            trace_session["fallback_reason"] = str(exc)

        mem = _load_memory()
        mem.append({"question": question, "intent": resp.intent, "answer": resp.answer})
        _save_memory(mem)
        trace_session["intent"] = resp.intent
        trace_session["answer"] = resp.answer
        trace_session["followups"] = resp.followups
        self._write_trace({"phase": "final", "session": trace_session})
        return resp
