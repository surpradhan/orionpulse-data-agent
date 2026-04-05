from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.orion_sales_agent.agent import OrionAgent  # noqa: E402


def _print_trace(step: str) -> None:
    """Print a single planner step to stderr during LLM execution."""
    print(f"  [TRACE] {step}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight local interface for OrionPulse Agent")
    parser.add_argument(
        "--question",
        required=False,
        default=None,
        help="Natural language or command-like question",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--mode",
        choices=["auto", "deterministic", "llm"],
        default=None,
        help="Execution mode for orchestration (defaults to ORION_CLI_DEFAULT_MODE)",
    )
    parser.add_argument(
        "--with-charts", action="store_true", help="Generate visualization insight pack"
    )
    parser.add_argument(
        "--with-analytics-exports",
        action="store_true",
        help="Generate Analytics Exports pack and semantic files",
    )
    parser.add_argument(
        "--reset-memory",
        action="store_true",
        help="Clear the conversation memory file and exit",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Print planner reasoning steps to stderr during LLM execution",
    )
    args = parser.parse_args()

    from src.orion_sales_agent.config import settings

    if args.reset_memory:
        memory_path = Path(settings.memory_file)
        memory_path.write_text("[]", encoding="utf-8")
        print(f"Memory cleared: {memory_path}")
        if not args.question:
            return

    if not args.question:
        parser.error("--question is required unless --reset-memory is used alone")

    execution_mode = args.mode or settings.cli_default_mode
    agent = OrionAgent()

    step_cb = _print_trace if args.trace else None
    resp = agent.answer(args.question, mode=execution_mode, step_callback=step_cb)

    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
        "execution_mode": resp.execution_mode,
    }
    if resp.fallback_reason:
        result["fallback_reason"] = resp.fallback_reason

    if args.with_charts:
        from src.orion_sales_agent.visualization import generate_insight_pack

        result["visuals"] = generate_insight_pack(args.question)

    if args.with_analytics_exports:
        from src.orion_sales_agent.analytics_exports import export_analytics_pack

        result["analytics_exports"] = export_analytics_pack(fmt="csv")

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
