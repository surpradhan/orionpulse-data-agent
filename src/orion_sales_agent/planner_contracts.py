"""Validation helpers for planner/critique/synthesis JSON contracts."""
from __future__ import annotations

from typing import Any


def validate_planner_plan(data: dict[str, Any]) -> dict[str, Any]:
    """Validate planner-step JSON contract."""

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


def validate_critique(data: dict[str, Any]) -> dict[str, Any]:
    """Validate critique-step JSON contract."""

    if not isinstance(data.get("continue"), bool):
        raise ValueError("Critique 'continue' must be boolean")
    if not isinstance(data.get("reason", ""), str):
        raise ValueError("Critique 'reason' must be string")
    return data


def validate_synthesis(data: dict[str, Any]) -> dict[str, Any]:
    """Validate synthesis-step JSON contract."""

    if not isinstance(data.get("answer", ""), str):
        raise ValueError("Synthesis 'answer' must be string")
    if "followups" in data and not isinstance(data.get("followups"), list):
        raise ValueError("Synthesis 'followups' must be array")
    return data
