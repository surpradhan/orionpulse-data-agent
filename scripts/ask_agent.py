from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.orion_sales_agent.agent import OrionAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight local interface for OrionPulse Agent")
    parser.add_argument("--question", required=True, help="Natural language or command-like question")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--with-charts", action="store_true", help="Generate visualization insight pack")
    parser.add_argument("--with-bi-exports", action="store_true", help="Generate BI export pack and semantic files")
    args = parser.parse_args()

    agent = OrionAgent()
    resp = agent.answer(args.question)
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
    }

    if args.with_charts:
        from src.orion_sales_agent.visualization import generate_insight_pack

        result["visuals"] = generate_insight_pack(args.question)

    if args.with_bi_exports:
        from src.orion_sales_agent.bi_exports import export_bi_pack

        result["bi_exports"] = export_bi_pack(fmt="csv")

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
