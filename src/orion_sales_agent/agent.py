"""Agent orchestration layer for OrionPulse.

This module provides deterministic and optional LLM-orchestrated answering flows,
tool execution routing, lightweight short-term memory persistence, and trace
artifact emission for debugging/operations.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .analytics import anomaly_detection, forecast_metric, kpi_summary
from .analytics_exports import export_analytics_pack
from .config import settings
from .db import query_df
from .llm_client import llm_chat, llm_enabled
from .memory_store import load_memory, save_memory
from .planner_contracts import validate_critique, validate_planner_plan, validate_synthesis
from .specs import dashboard_spec, storyboard_spec
from .sql_policy import validate_readonly_select
from .tool_registry import build_tool_registry
from .visualization import generate_insight_pack

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(settings.skills_dir)
MEMORY_FILE = Path(settings.memory_file)

# Thread-safety: guards load/append/save of the conversation memory file so
# concurrent requests cannot overwrite each other's records.
_MEMORY_LOCK = threading.Lock()

# Maximum characters allowed per tool-result entry in the LLM observation
# list.  Results exceeding this are replaced with a truncated preview to
# prevent LLM context-window overflows on large datasets.
_OBS_RESULT_MAX_CHARS: int = 4_000

# Tables/views that agent-internal queries are permitted to reference.
# Used for defence-in-depth validation of all query_df call sites.
_SQL_ALLOWED_OBJECTS: set[str] = {
    "fact_sales",
    "dim_product",
    "dim_region",
    "vw_region_performance",
    "vw_product_margin_rank",
    "vw_monthly_sales",
}

_HTML_TAG_RE = re.compile(r"<[^>]{0,200}>")


def _sanitize_text(text: str | None) -> str | None:
    """Strip HTML/script tags from LLM-generated text to prevent XSS injection.

    Applied to all LLM-produced answer strings before they leave the agent
    layer. Uses a bounded regex so pathologically long tag-like strings cannot
    cause catastrophic backtracking.

    Args:
        text: Raw string from LLM or synthesizer, may be None.

    Returns:
        Sanitized string with HTML tags removed, or the original value when
        ``text`` is None/empty (preserving falsy semantics for callers).
    """
    if not text:
        return text
    cleaned = _HTML_TAG_RE.sub("", text)
    # Collapse runs of whitespace introduced by tag removal
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


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
        self._tools = build_tool_registry()

    def _trace_enabled(self) -> bool:
        """Return whether JSON trace artifacts should be written."""
        return settings.debug_trace

    def _write_trace(self, payload: dict[str, Any]) -> None:
        """Write a timestamped trace artifact when tracing is enabled."""
        if not self._trace_enabled():
            return
        out_dir = Path(settings.trace_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
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
        return self._tools

    def _rule_based_answer(
        self, question: str, execution_mode: str = "deterministic"
    ) -> AgentResponse:
        """Produce a deterministic answer using intent-driven routing.

        This path is used for explicit deterministic mode and as safety fallback
        when LLM orchestration is unavailable or fails.
        """
        intent = self.classify_intent(question)
        reasoning = [
            f"Classified intent as '{intent}'",
            "Retrieved relevant skills context and selected toolchain",
        ]
        data: Any = None

        if intent == "forecast":
            data = forecast_metric(settings.db_path, horizon=settings.default_forecast_horizon)
            answer = self._synthesize_forecast_answer(question, data)
            followups = [
                "Do you want forecast split by region?",
                "Should I compare forecast vs last year?",
            ]
        elif intent == "anomaly":
            data = anomaly_detection(settings.db_path)
            answer = self._synthesize_anomaly_answer(question, data)
            followups = ["Should I explain probable drivers for each anomaly?"]
        elif intent == "dashboard":
            data = dashboard_spec()
            answer = self._synthesize_dashboard_answer(question, data)
            followups = ["Need an operations-focused dashboard variant?"]
        elif intent == "storyboard":
            data = storyboard_spec(goal=question)
            answer = self._synthesize_storyboard_answer(question, data)
            followups = ["Should I tailor this for CFO audience?"]
        elif intent == "root_cause":
            data = self._root_cause_pack()
            answer = self._synthesize_root_cause_answer(question, data)
            followups = ["Want me to convert this into action recommendations?"]
        elif intent == "region":
            data = self._region_pack()
            answer = self._synthesize_region_answer(question, data)
            followups = [
                "Want a forecast for the top-performing region?",
                "Should I break this down by product within each region?",
            ]
        elif intent == "kpi":
            data = kpi_summary(settings.db_path)
            answer = self._synthesize_kpi_answer(question, data)
            followups = ["Need quarter-over-quarter or YoY comparison?"]
        elif (
            "chart" in question.lower()
            or "visual" in question.lower()
            or "graph" in question.lower()
        ):
            data = generate_insight_pack(question)
            answer = "Generated visualization insight pack with saved chart artifacts."
            followups = [
                "Do you want SVG exports as well?",
                "Should I include anomaly and forecast charts?",
            ]
        elif (
            "analytics export" in question.lower()
            or "semantic export" in question.lower()
            or "export pack" in question.lower()
        ):
            data = export_analytics_pack(fmt="csv")
            answer = (
                "Generated Analytics Export pack with canonical datasets"
                " and semantic mapping files."
            )
            followups = [
                "Should I also generate parquet exports?",
                "Need tool-specific starter templates refined further?",
            ]
        else:
            data = {
                "message": (
                    "I can help with KPI summary, root-cause analysis, forecasts,"
                    " anomalies, dashboards, and storyboards."
                ),
                "skills_loaded": sorted(self.skills.keys()),
            }
            answer = "Mapped your request to available analytical capabilities."
            followups = [
                "Try: 'forecast next 3 months revenue'",
                "Try: 'why did margin drop in APAC?'",
            ]

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
                    answer=_sanitize_text(
                        str(plan.get("final_answer", "Generated final response."))
                    ) or "",
                    data={"observations": observations},
                    reasoning_summary=reasoning,
                    followups=plan.get("followups", []),
                    execution_mode="llm_orchestrated",
                )

            action = plan.get("action")
            if not action or not isinstance(action, dict):
                observations.append({
                    "step": step,
                    "error": "Planner returned final=false but action is missing or null",
                })
                continue
            tool = action.get("tool")
            args = action.get("args") or {}
            if tool not in tools:
                observations.append({"tool": tool, "error": "Invalid tool requested by planner"})
                continue

            try:
                out = tools[tool](args)
                # Guard against oversized tool results overflowing the LLM
                # context window.  Serialise to measure, then truncate if needed.
                raw_result = json.dumps(out, ensure_ascii=False, default=str)
                if len(raw_result) > _OBS_RESULT_MAX_CHARS:
                    result_payload: Any = {
                        "_truncated": True,
                        "char_count": len(raw_result),
                        "preview": raw_result[:_OBS_RESULT_MAX_CHARS],
                    }
                else:
                    result_payload = out
                observations.append({"tool": tool, "args": args, "result": result_payload})
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
            critique_user = json.dumps(
                {"question": question, "observations": observations}, ensure_ascii=False
            )
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
        synth_user = json.dumps(
            {"question": question, "observations": observations}, ensure_ascii=False
        )
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
            answer=_sanitize_text(str(synth.get("answer", "Completed multi-hop analysis."))) or "",
            data={"observations": observations},
            reasoning_summary=reasoning,
            followups=synth.get("followups", []),
            execution_mode="llm_orchestrated",
        )

    def classify_intent(self, question: str) -> str:
        """Classify user intent using lightweight keyword heuristics.

        Keyword precedence is ordered from most specific to least specific.
        Generic words ("compare", "breakdown", "product", "why") are only
        matched when accompanied by domain-specific context to avoid
        misrouting unrelated questions.
        """
        q = question.lower()
        if "forecast" in q or "predict" in q:
            return "forecast"
        if "anomaly" in q or "outlier" in q or "spike" in q:
            return "anomaly"
        if "dashboard" in q:
            return "dashboard"
        if "storyboard" in q or "narrative" in q:
            return "storyboard"
        # "why" alone is too generic — require a business-outcome word alongside it.
        _why_context = {
            "drop", "decline", "increase", "margin", "revenue", "down", "up",
            "spike", "fall", "fell", "rose", "grew", "missed", "beat",
        }
        if (
            "root cause" in q
            or "driver" in q
            or ("why" in q and any(kw in q for kw in _why_context))
        ):
            return "root_cause"
        # Region/leaderboard intent — narrow the generic catch-all terms so that
        # "compare forecast", "product summary", "breakdown by month" etc. don't
        # accidentally land here.
        if (
            "region" in q
            or "leaderboard" in q
            or "ranking" in q
            or "by region" in q
            or "by country" in q
            or "by channel" in q
            or "top product" in q
            or "product margin" in q
            or "product rank" in q
            or "margin rank" in q
            or ("compare" in q and any(
                kw in q for kw in {"region", "country", "channel", "apac", "emea", "latam"}
            ))
            or ("breakdown" in q and any(kw in q for kw in {"region", "country", "channel"}))
            or ("product" in q and any(
                kw in q for kw in {"top", "rank", "margin", "best", "worst"}
            ))
        ):
            return "region"
        if "kpi" in q or "summary" in q or "performance" in q:
            return "kpi"
        return "general"

    def _region_pack(self) -> dict:
        """Build ranked region + product data for leaderboard / comparison questions."""
        region_sql = """
            SELECT region_name, country, sales_channel,
                   SUM(net_revenue) AS net_revenue,
                   SUM(margin)      AS margin,
                   SUM(units_sold)  AS units_sold,
                   AVG(margin_pct)  AS margin_pct
            FROM vw_region_performance
            GROUP BY region_name, country, sales_channel
            ORDER BY net_revenue DESC
        """
        product_sql = "SELECT * FROM vw_product_margin_rank ORDER BY margin_pct DESC"
        validate_readonly_select(region_sql, _SQL_ALLOWED_OBJECTS)
        validate_readonly_select(product_sql, _SQL_ALLOWED_OBJECTS)
        regions = query_df(settings.db_path, region_sql).to_dict(orient="records")
        products = query_df(settings.db_path, product_sql).to_dict(orient="records")
        return {"regions": regions, "products": products}

    def _synthesize_region_answer(self, question: str, data: dict) -> str:
        """Turn the region pack into a plain-English ranked summary."""
        regions: list[dict] = data.get("regions", [])
        products: list[dict] = data.get("products", [])
        q_lower = question.lower()

        parts: list[str] = []

        if regions:
            sorted_rev = sorted(regions, key=lambda r: r["net_revenue"], reverse=True)
            sorted_margin = sorted(regions, key=lambda r: r["margin_pct"], reverse=True)
            leader = sorted_rev[0]
            trailer = sorted_rev[-1]

            # Revenue leaderboard
            rank_lines = "  |  ".join(
                f"#{i+1} {r['region_name']} ${r['net_revenue']:,.0f}"
                for i, r in enumerate(sorted_rev)
            )
            parts.append(f"Revenue leaderboard: {rank_lines}.")

            # Gap between top and bottom
            gap_pct = (leader["net_revenue"] - trailer["net_revenue"]) / leader["net_revenue"] * 100
            parts.append(
                f"{leader['region_name']} leads at ${leader['net_revenue']:,.0f} "
                f"({leader['units_sold']:,} units, {leader['sales_channel']} channel); "
                f"{trailer['region_name']} trails by {gap_pct:.1f}%."
            )

            # Margin leader vs revenue leader
            margin_leader = sorted_margin[0]
            if margin_leader["region_name"] != leader["region_name"]:
                parts.append(
                    f"Note: {margin_leader['region_name']} tops on margin rate "
                    f"({margin_leader['margin_pct']*100:.1f}%) even though "
                    f"{leader['region_name']} wins on revenue — "
                    f"different regions lead on volume vs. profitability."
                )
            else:
                parts.append(
                    f"{margin_leader['region_name']} leads on both revenue and margin rate "
                    f"({margin_leader['margin_pct']*100:.1f}%), making it the strongest"
                    " region overall."
                )

        # Product angle if question mentions products/margin
        if products and ("product" in q_lower or "margin" in q_lower or "rank" in q_lower):
            top_p = products[0]
            low_p = products[-1]
            parts.append(
                f"Top product by margin: '{top_p['product_name']}' ({top_p['category']}) "
                f"at {top_p['margin_pct']*100:.1f}% on ${top_p['net_revenue']:,.0f} revenue. "
                f"Lowest: '{low_p['product_name']}' at {low_p['margin_pct']*100:.1f}%."
            )

        return " ".join(parts)

    def _synthesize_forecast_answer(self, question: str, data: dict) -> str:
        """Turn forecast data into a plain-English answer."""
        pts = data.get("forecast", [])
        diag = data.get("diagnostics", {})
        metric = data.get("metric", "net_revenue").replace("_", " ")
        q_lower = question.lower()

        parts: list[str] = []

        # Resolve which region the question refers to.
        # Look up actual region names from the DB rather than a hardcoded list
        # so the detection works regardless of how the data was seeded.
        try:
            _rdf = query_df(
                settings.db_path,
                "SELECT DISTINCT region_name FROM vw_region_performance",
            )
            _known_regions: list[str] = (
                [r["region_name"] for r in _rdf.to_dict(orient="records")]
                if not _rdf.empty
                else []
            )
        except Exception:
            _known_regions = []

        region_hint = next(
            (r for r in _known_regions if r.lower() in q_lower),
            None,
        )
        # Resolve semantic references like "top-performing", "best", "leading"
        if not region_hint and any(
            kw in q_lower for kw in ["top", "best", "leading", "highest", "number one", "#1"]
        ):
            try:
                df = query_df(
                    settings.db_path,
                    "SELECT region_name, SUM(net_revenue) AS rev FROM vw_region_performance "
                    "GROUP BY region_name ORDER BY rev DESC LIMIT 1",
                )
                # iloc[0] crash guard: only access if the DataFrame is non-empty
                if not df.empty:
                    top = df.iloc[0]
                    region_hint = top["region_name"]
                    parts.append(
                        f"The top-performing region by revenue is {region_hint} "
                        f"(${top['rev']:,.0f} total). "
                        f"Region-level forecasting is not yet supported, so the forecast below "
                        f"covers overall net revenue as the best available proxy for {region_hint}."
                    )
            except Exception:
                pass
        elif region_hint:
            parts.append(
                f"Note: region-level forecasting is not yet supported — "
                f"showing overall {metric} forecast as the best available proxy for {region_hint}."
            )
        scope = f"{region_hint} " if region_hint else ""

        if pts:
            first, last = pts[0], pts[-1]
            # ZeroDivisionError guard: treat zero-base as flat
            delta_ratio = (
                abs(last["value"] - first["value"]) / first["value"] if first["value"] else 0
            )
            trend = "flat" if delta_ratio < 0.02 else (
                "upward" if last["value"] > first["value"] else "downward"
            )
            parts.append(
                f"The {scope}{metric} forecast shows a {trend} trend"
                f" over the next {len(pts)} month(s): "
                + ", ".join(f"{p['period']} ${p['value']:,.0f}" for p in pts) + "."
            )
            parts.append(
                f"95% confidence band widens to ${pts[-1]['lower']:,.0f}–${pts[-1]['upper']:,.0f} "
                f"by {pts[-1]['period']}."
            )

        if diag:
            mape = diag.get("mape")
            method = diag.get("method", "").replace("_", " ")
            # mape=None guard: skip quality rating when mape is unavailable
            if mape is not None:
                quality = "excellent" if mape < 5 else "good" if mape < 10 else "moderate"
                parts.append(
                    f"Model: {method}, MAPE {mape:.1f}% ({quality} fit), "
                    f"selected over {len(diag.get('candidates', []))} candidate(s)"
                    " by backtest RMSE."
                )
            elif method:
                parts.append(f"Model: {method} (MAPE not available for this run).")

        return (
            " ".join(parts) if parts
            else "Forecast computed — no periods returned for the configured horizon."
        )

    def _synthesize_anomaly_answer(self, question: str, data: list) -> str:
        """Turn anomaly detection results into a plain-English answer."""
        if not data:
            return (
                "No anomalies detected in net revenue at the configured z-score threshold — "
                "the series looks statistically clean."
            )
        parts: list[str] = []
        parts.append(f"{len(data)} anomalous period(s) detected:")
        for a in data:
            direction = "above" if a["zscore"] > 0 else "below"
            severity = "strong" if abs(a["zscore"]) > 3 else "moderate"
            parts.append(
                f"{a['period']}: ${a['value']:,.0f} — {severity} {direction}-mean spike "
                f"(z={a['zscore']:.2f})."
            )
        if len(data) == 1:
            parts.append(
                "A single outlier is unlikely to indicate a systemic issue — "
                "check for one-off deals, data errors, or seasonal effects in that month."
            )
        else:
            parts.append(
                "Multiple anomalies may suggest a recurring seasonal pattern"
                " or a data quality issue worth investigating."
            )
        return " ".join(parts)

    def _synthesize_kpi_answer(self, question: str, data: dict) -> str:
        """Turn KPI summary data into a plain-English answer."""
        if not data:
            return "KPI summary computed — no data returned."

        parts: list[str] = []

        # kpi_summary() always returns list[dict]; guard for unexpected callers.
        rows: list[dict] = data if isinstance(data, list) else []

        if rows:
            # sort by period if possible
            try:
                rows = sorted(rows, key=lambda r: r.get("period", ""))
            except Exception:
                pass

            latest = rows[-1] if rows else {}
            earliest = rows[0] if rows else {}

            rev_key = next((k for k in latest if "revenue" in k.lower()), None)
            margin_key = next(
                (k for k in latest if "margin_pct" in k.lower() or "margin_%" in k.lower()),
                None,
            )
            period_key = next((k for k in latest if "period" in k.lower()), None)

            if rev_key and period_key:
                latest_rev = latest.get(rev_key, 0)
                earliest_rev = earliest.get(rev_key, 0)
                pct_change = (
                    (latest_rev - earliest_rev) / earliest_rev * 100 if earliest_rev else 0
                )
                direction = "up" if pct_change > 0 else "down"
                parts.append(
                    f"Latest period ({latest.get(period_key, '?')}): "
                    f"net revenue ${latest_rev:,.0f} — "
                    f"{direction} {abs(pct_change):.1f}% vs. the start of the tracked window "
                    f"({earliest.get(period_key, '?')}: ${earliest_rev:,.0f})."
                )

            if margin_key:
                margins = [r.get(margin_key, 0) for r in rows if r.get(margin_key) is not None]
                if margins:
                    avg_m = sum(margins) / len(margins)
                    parts.append(
                        f"Average margin rate across {len(rows)} periods: {avg_m*100:.1f}%."
                    )

        if not parts:
            parts.append(f"KPI summary computed across {len(rows)} periods.")

        return " ".join(parts)

    def _root_cause_pack(self) -> dict:
        """Build a multi-source driver pack for root-cause style questions."""
        region_sql = "SELECT * FROM vw_region_performance ORDER BY net_revenue DESC LIMIT 5"
        product_sql = "SELECT * FROM vw_product_margin_rank ORDER BY margin_pct DESC LIMIT 5"
        validate_readonly_select(region_sql, _SQL_ALLOWED_OBJECTS)
        validate_readonly_select(product_sql, _SQL_ALLOWED_OBJECTS)
        region = query_df(settings.db_path, region_sql).to_dict(orient="records")
        product = query_df(settings.db_path, product_sql).to_dict(orient="records")
        anomalies = anomaly_detection(settings.db_path)
        return {"region_drivers": region, "product_drivers": product, "anomalies": anomalies}

    def _synthesize_root_cause_answer(self, question: str, data: dict) -> str:
        """Turn the root-cause data pack into a plain-English answer."""
        regions: list[dict] = data.get("region_drivers", [])
        products: list[dict] = data.get("product_drivers", [])
        anomalies: list[dict] = data.get("anomalies", [])

        # --- detect which region the question is about ---
        q_lower = question.lower()
        focus_region = next(
            (r["region_name"] for r in regions if r["region_name"].lower() in q_lower),
            None,
        )

        parts: list[str] = []

        if focus_region and regions:
            sorted_regions = sorted(regions, key=lambda r: r["margin_pct"], reverse=True)
            focus = next((r for r in regions if r["region_name"] == focus_region), None)
            top = sorted_regions[0]
            if focus:
                gap_pp = (top["margin_pct"] - focus["margin_pct"]) * 100
                rank = sorted_regions.index(focus) + 1
                parts.append(
                    f"{focus_region} margin sits at {focus['margin_pct']*100:.1f}% "
                    f"(#{rank} of {len(regions)}), trailing {top['region_name']} "
                    f"({top['margin_pct']*100:.1f}%) by {gap_pp:.1f} percentage points."
                )
                # revenue context
                parts.append(
                    f"Revenue is healthy at ${focus['net_revenue']:,.0f} "
                    f"({focus['units_sold']:,} units via {focus['sales_channel']} channel), "
                    f"so the gap is a rate issue, not a volume problem."
                )
        elif regions:
            sorted_regions = sorted(regions, key=lambda r: r["margin_pct"], reverse=True)
            top, bottom = sorted_regions[0], sorted_regions[-1]
            gap_pp = (top["margin_pct"] - bottom["margin_pct"]) * 100
            parts.append(
                f"Margin ranges from {bottom['margin_pct']*100:.1f}% ({bottom['region_name']}) "
                f"to {top['margin_pct']*100:.1f}% ({top['region_name']}), "
                f"a spread of {gap_pp:.1f} percentage points."
            )

        # --- product mix driver ---
        if products:
            sorted_prods = sorted(products, key=lambda p: p["margin_pct"])
            low_p = sorted_prods[0]
            high_p = sorted_prods[-1]
            parts.append(
                f"The primary product driver is mix: '{high_p['product_name']}' "
                f"({high_p['category']}) leads at {high_p['margin_pct']*100:.1f}% margin, "
                f"while '{low_p['product_name']}' ({low_p['category']}) trails "
                f"at {low_p['margin_pct']*100:.1f}%. "
                f"If {focus_region or 'the lagging region'} skews toward lower-margin SKUs, "
                f"that alone explains the gap."
            )

        # --- anomaly context ---
        if anomalies:
            a = anomalies[0]
            direction = "spike" if a["zscore"] > 0 else "dip"
            parts.append(
                f"Note: {a['period']} shows a revenue {direction} "
                f"(z={a['zscore']:.2f}, value=${a['value']:,.0f}) — "
                f"this is a one-period outlier, not a sustained margin trend."
            )
        else:
            parts.append(
                "No statistical anomalies detected — the margin gap is structural,"
                " not event-driven."
            )

        return " ".join(parts)

    def _synthesize_dashboard_answer(self, question: str, data: dict) -> str:
        """Turn a dashboard spec into a plain-English summary."""
        widgets = data.get("widgets", [])
        if not widgets:
            return "Dashboard specification generated with KPI and trend widgets."
        kpi_count = sum(1 for w in widgets if "kpi" in str(w.get("type", "")).lower())
        chart_count = len(widgets) - kpi_count
        widget_names = [w.get("title") or w.get("type", "widget") for w in widgets]
        parts = [
            f"Dashboard specification generated with {len(widgets)} widget(s): "
            f"{kpi_count} KPI tile(s) and {chart_count} chart(s)."
        ]
        if widget_names:
            parts.append(
                "Widgets: " + ", ".join(str(n) for n in widget_names[:6])
                + ("…" if len(widget_names) > 6 else "") + "."
            )
        return " ".join(parts)

    def _synthesize_storyboard_answer(self, question: str, data: dict) -> str:
        """Turn a storyboard spec into a plain-English summary."""
        slides = data.get("slides", [])
        goal = data.get("goal", question)
        if not slides:
            return (
                "Executive storyboard generated "
                "(context → insights → prediction → recommended actions)."
            )
        titles = [s.get("title", f"Slide {i+1}") for i, s in enumerate(slides)]
        return (
            f"Executive storyboard generated for: \"{goal}\". "
            f"{len(slides)} slide(s): "
            + " → ".join(str(t) for t in titles) + "."
        )

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
            "timestamp": datetime.now(UTC).isoformat(),
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
            logger.error(
                "Agent orchestration failed, falling back to rule-based: %s", exc, exc_info=True
            )
            resp = self._rule_based_answer(question, execution_mode="fallback_rule_based")
            resp.fallback_reason = str(exc)
            trace_session["mode"] = "fallback_rule_based"
            trace_session["fallback_reason"] = str(exc)

        with _MEMORY_LOCK:
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
