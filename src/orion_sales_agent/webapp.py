from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent import OrionAgent
from .analytics import forecast_metric, kpi_summary
from .config import settings


def _auth_is_configured() -> bool:
    return bool(settings.analyst_token.strip() or settings.admin_token.strip())


def _startup_auth_guard() -> None:
    if settings.auth_required and not _auth_is_configured():
        raise RuntimeError(
            "ORION_AUTH_REQUIRED=true but no ORION_ANALYST_TOKEN/ORION_ADMIN_TOKEN configured"
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _startup_auth_guard()
    yield


app = FastAPI(title="OrionPulse Agent UI", lifespan=lifespan)
agent = OrionAgent()
app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")
app.mount("/specs", StaticFiles(directory="specs"), name="specs")


def _response_envelope(data, warnings: list[str] | None = None) -> dict:
    return {
        "status": "ok",
        "trace_id": f"orion-{uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings or [],
        "data": data,
    }


def _require_role(x_orion_token: str | None, required_role: str) -> None:
    token = (x_orion_token or "").strip()
    # If auth is not required and tokens are not configured, keep local/dev mode open.
    if not settings.auth_required and not _auth_is_configured():
        return

    if required_role == "analyst":
        if settings.analyst_token and token == settings.analyst_token:
            return
        if settings.admin_token and token == settings.admin_token:
            return
        raise HTTPException(status_code=401, detail="Unauthorized: analyst token required")
    if required_role == "admin":
        if settings.admin_token and token == settings.admin_token:
            return
        raise HTTPException(status_code=403, detail="Forbidden: admin token required")
    raise HTTPException(status_code=500, detail="Invalid role requirement")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
      <head>
        <title>OrionPulse Agent</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 0; background: #f6f8fb; }
          .wrap { max-width: 920px; margin: 24px auto; padding: 0 16px; }
          .card { background: #fff; border: 1px solid #e4e8f0; border-radius: 12px; padding: 16px; }
          h2 { margin-top: 0; }
          textarea { width: 100%; min-height: 90px; padding: 10px; border-radius: 8px; border: 1px solid #cdd5e1; }
          .row { display: flex; gap: 12px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
          button { background: #1f6feb; color: #fff; border: 0; border-radius: 8px; padding: 9px 14px; cursor: pointer; }
          button:disabled { opacity: 0.6; cursor: not-allowed; }
          .out { white-space: pre-wrap; background: #0b1020; color: #d9e0ff; border-radius: 8px; padding: 12px; margin-top: 14px; max-height: 420px; overflow: auto; }
          .muted { color: #566076; font-size: 13px; }
        </style>
      </head>
      <body>
        <div class='wrap'>
          <div class='card'>
            <h2>OrionPulse Agent</h2>
            <p class='muted'>Ask business questions, optionally generate charts and BI export packs.</p>
            <textarea id='q' placeholder='Example: why did margin drop in APAC and show charts'></textarea>
            <div class='row'>
              <label><input type='checkbox' id='withVisuals' checked /> Include visuals</label>
              <label><input type='checkbox' id='withBI' /> Include BI exports</label>
              <label><input type='checkbox' id='autoSpeak' checked /> Auto speak answer</label>
              <select id='fmt'>
                <option value='png'>png</option>
                <option value='svg'>svg</option>
                <option value='csv'>csv (BI)</option>
              </select>
              <button id='askBtn' onclick='askAgent()'>Ask Agent</button>
              <button id='micBtn' onclick='toggleMic()'>🎤 Start Listening</button>
              <button id='stopSpeakBtn' onclick='stopSpeaking()'>⏹ Stop Voice</button>
            </div>
            <div class='row'>
              <label>Voice:
                <select id='voiceSelect'></select>
              </label>
              <label>Rate:
                <input id='rate' type='range' min='0.7' max='1.3' step='0.1' value='1.0' />
              </label>
              <span id='micStatus' class='muted'>Mic: idle</span>
            </div>
            <div id='out' class='out'>Response will appear here...</div>
          </div>
        </div>
        <script>
          let recognition = null;
          let recognizing = false;
          let voices = [];

          function loadVoices() {
            voices = speechSynthesis.getVoices() || [];
            const sel = document.getElementById('voiceSelect');
            sel.innerHTML = '';
            voices.forEach((v, i) => {
              const opt = document.createElement('option');
              opt.value = String(i);
              opt.textContent = `${v.name} (${v.lang})`;
              sel.appendChild(opt);
            });
            if (!voices.length) {
              const opt = document.createElement('option');
              opt.value = '-1';
              opt.textContent = 'Default voice';
              sel.appendChild(opt);
            }
          }

          function initMic() {
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) {
              document.getElementById('micStatus').textContent = 'Mic: SpeechRecognition not supported';
              document.getElementById('micBtn').disabled = true;
              return;
            }
            recognition = new SR();
            recognition.lang = 'en-US';
            recognition.interimResults = true;
            recognition.continuous = false;
            recognition.onstart = () => {
              recognizing = true;
              document.getElementById('micStatus').textContent = 'Mic: listening...';
              document.getElementById('micBtn').textContent = '🛑 Stop Listening';
            };
            recognition.onend = () => {
              recognizing = false;
              document.getElementById('micStatus').textContent = 'Mic: idle';
              document.getElementById('micBtn').textContent = '🎤 Start Listening';
            };
            recognition.onresult = (e) => {
              let transcript = '';
              for (let i = e.resultIndex; i < e.results.length; i++) {
                transcript += e.results[i][0].transcript;
              }
              document.getElementById('q').value = transcript.trim();
            };
            recognition.onerror = (e) => {
              document.getElementById('micStatus').textContent = 'Mic error: ' + e.error;
            };
          }

          function toggleMic() {
            if (!recognition) return;
            if (recognizing) recognition.stop();
            else recognition.start();
          }

          function stopSpeaking() {
            speechSynthesis.cancel();
          }

          function speakText(text) {
            if (!text) return;
            if (!('speechSynthesis' in window)) return;
            speechSynthesis.cancel();
            const utt = new SpeechSynthesisUtterance(text);
            const sel = document.getElementById('voiceSelect');
            const idx = Number(sel.value || -1);
            if (idx >= 0 && voices[idx]) utt.voice = voices[idx];
            utt.rate = Number(document.getElementById('rate').value || 1.0);
            speechSynthesis.speak(utt);
          }

          async function askAgent() {
            const q = document.getElementById('q').value.trim();
            const withVisuals = document.getElementById('withVisuals').checked;
            const withBI = document.getElementById('withBI').checked;
            const autoSpeak = document.getElementById('autoSpeak').checked;
            const fmt = document.getElementById('fmt').value;
            const out = document.getElementById('out');
            const btn = document.getElementById('askBtn');
            if (!q) { out.textContent = 'Please enter a question.'; return; }
            btn.disabled = true;
            out.textContent = 'Thinking...';
            try {
              const resp = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ q, with_visuals: withVisuals, with_bi: withBI, fmt })
              });
              const data = await resp.json();
              out.textContent = JSON.stringify(data, null, 2);
              if (autoSpeak && data && data.answer) speakText(data.answer);
            } catch (e) {
              out.textContent = 'Error: ' + e;
            } finally {
              btn.disabled = false;
            }
          }

          window.speechSynthesis?.addEventListener?.('voiceschanged', loadVoices);
          loadVoices();
          initMic();
        </script>
      </body>
    </html>
    """


@app.post("/chat")
def chat(payload: dict, x_orion_token: str | None = Header(default=None)):
    _require_role(x_orion_token, "analyst")

    q = str(payload.get("q", "")).strip()
    if not q:
        return JSONResponse(status_code=400, content={"error": "q is required"})
    with_visuals = bool(payload.get("with_visuals", False))
    with_bi = bool(payload.get("with_bi", False))
    fmt = str(payload.get("fmt", "png"))

    resp = agent.answer(q)
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
    }

    if with_visuals:
        from .visualization import generate_insight_pack

        vfmt = fmt if fmt in {"png", "svg"} else "png"
        result["visuals"] = generate_insight_pack(q, fmt=vfmt)
    if with_bi:
        _require_role(x_orion_token, "admin")
        from .bi_exports import export_bi_pack

        bfmt = fmt if fmt in {"csv", "parquet"} else "csv"
        result["bi_exports"] = export_bi_pack(fmt=bfmt)
    return _response_envelope(result)


@app.get("/kpi")
def kpi(x_orion_token: str | None = Header(default=None)):
    _require_role(x_orion_token, "analyst")
    return _response_envelope(kpi_summary(settings.db_path))


@app.get("/forecast")
def forecast(x_orion_token: str | None = Header(default=None)):
    _require_role(x_orion_token, "analyst")
    out = forecast_metric(settings.db_path)
    warnings: list[str] = []
    if out.get("warning"):
        warnings.append(str(out.get("warning")))
    return _response_envelope(out, warnings=warnings)


@app.get("/ask")
def ask(q: str = Query(..., min_length=3, max_length=400), x_orion_token: str | None = Header(default=None)):
    _require_role(x_orion_token, "analyst")
    resp = agent.answer(q)
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
    }
    return _response_envelope(result)


@app.get("/ask_with_visuals")
def ask_with_visuals(
    q: str = Query(..., min_length=3, max_length=400),
    fmt: str = Query("png"),
    x_orion_token: str | None = Header(default=None),
):
    _require_role(x_orion_token, "analyst")
    from .visualization import generate_insight_pack

    resp = agent.answer(q)
    visuals = generate_insight_pack(q, fmt=fmt)
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
        "visuals": visuals,
        "artifacts_base": "/artifacts/charts",
    }
    return _response_envelope(result)


@app.get("/ask_with_bi_exports")
def ask_with_bi_exports(
    q: str = Query(..., min_length=3, max_length=400),
    fmt: str = Query("csv"),
    x_orion_token: str | None = Header(default=None),
):
    _require_role(x_orion_token, "admin")
    from .bi_exports import export_bi_pack

    resp = agent.answer(q)
    bi_pack = export_bi_pack(fmt=fmt)
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
        "bi_exports": bi_pack,
        "artifacts_base": "/artifacts/bi_exports",
        "semantic_specs_base": "/specs/bi",
    }
    return _response_envelope(result)
