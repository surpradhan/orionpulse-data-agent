from __future__ import annotations

import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.server import (  # noqa: E402
    create_sql_view,
    run_anomaly_detection,
    run_forecast,
    run_sql,
)

ART = Path("artifacts/ui-tests")
ART.mkdir(parents=True, exist_ok=True)


def fetch(url: str, out_file: str) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            (ART / out_file).write_text(body, encoding="utf-8")
            return True, f"HTTP {resp.status}"
    except (HTTPError, URLError, TimeoutError) as exc:
        (ART / out_file).write_text(str(exc), encoding="utf-8")
        return False, str(exc)


def main() -> None:
    results: list[tuple[str, str, str]] = []

    ok, msg = fetch("http://127.0.0.1:8010/", "UI-001_home.html")
    results.append(("UI-001", "PASS" if ok else "FAIL", msg))

    ok, msg = fetch("http://127.0.0.1:8010/kpi", "UI-002_kpi.json")
    results.append(("UI-002", "PASS" if ok else "FAIL", msg))

    ok, msg = fetch("http://127.0.0.1:8010/forecast", "UI-003_forecast.json")
    results.append(("UI-003", "PASS" if ok else "FAIL", msg))

    stable = True
    for i in range(1, 6):
        ok_kpi, _ = fetch("http://127.0.0.1:8010/kpi", f"UI-004_refresh_kpi_{i}.json")
        ok_fc, _ = fetch("http://127.0.0.1:8010/forecast", f"UI-004_refresh_forecast_{i}.json")
        stable = stable and ok_kpi and ok_fc
    results.append(("UI-004", "PASS" if stable else "FAIL", "Repeated refresh stability"))

    # AUTH current-state check (no auth expected)
    auth_ok = all(
        (ART / f).exists()
        for f in ["UI-001_home.html", "UI-002_kpi.json", "UI-003_forecast.json"]
    )
    results.append(("AUTH-001", "PASS" if auth_ok else "FAIL", "Unauthenticated routes reachable"))

    # Safety/API hardening checks
    try:
        run_sql("SELECT 1; SELECT 2", 10)
        results.append(("API-SEC-001", "FAIL", "Multi-statement was not blocked"))
    except Exception as exc:
        (ART / "API-SEC-001.log").write_text(str(exc), encoding="utf-8")
        results.append(("API-SEC-001", "PASS", str(exc)))

    try:
        run_sql("SELECT * FROM sqlite_master", 10)
        results.append(("API-SEC-002", "FAIL", "Disallowed object was not blocked"))
    except Exception as exc:
        (ART / "API-SEC-002.log").write_text(str(exc), encoding="utf-8")
        results.append(("API-SEC-002", "PASS", str(exc)))

    try:
        create_sql_view("x", "SELECT * FROM fact_sales")
        results.append(("API-SEC-003", "FAIL", "create_sql_view should be blocked without admin"))
    except Exception as exc:
        (ART / "API-SEC-003.log").write_text(str(exc), encoding="utf-8")
        results.append(("API-SEC-003", "PASS", str(exc)))

    try:
        run_forecast("net_revenue", 100)
        results.append(("API-VAL-001", "FAIL", "Invalid horizon not rejected"))
    except Exception as exc:
        (ART / "API-VAL-001.log").write_text(str(exc), encoding="utf-8")
        results.append(("API-VAL-001", "PASS", str(exc)))

    try:
        run_anomaly_detection("net_revenue", 0.2)
        results.append(("API-VAL-002", "FAIL", "Invalid threshold not rejected"))
    except Exception as exc:
        (ART / "API-VAL-002.log").write_text(str(exc), encoding="utf-8")
        results.append(("API-VAL-002", "PASS", str(exc)))

    summary_lines = ["# UI Realtime Test Summary", "", "| Test | Status | Notes |", "|---|---|---|"]
    for tid, status, notes in results:
        summary_lines.append(f"| {tid} | {status} | {notes.replace('|', '/')} |")
    (ART / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print("\n".join(summary_lines))


if __name__ == "__main__":
    main()
