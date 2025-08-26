# ui/app.py
import os, time, base64, json, requests
import streamlit as st

BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
BASIC_USER = os.getenv("BASIC_USER", "admin")
BASIC_PASS = os.getenv("BASIC_PASS", "password")

def _auth_header():
    token = base64.b64encode(f"{BASIC_USER}:{BASIC_PASS}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

def api_get(path):
    try:
        r = requests.get(f"{BACKEND}{path}", headers=_auth_header(), timeout=15)
        return r.status_code == 200, (r.json() if r.content else {})
    except Exception as e:
        return False, {"error": str(e)}

def api_post(path, payload):
    try:
        r = requests.post(f"{BACKEND}{path}", headers={"Content-Type":"application/json", **_auth_header()}, json=payload, timeout=30)
        ok = r.status_code == 200
        return ok, (r.json() if ok and r.content else {"http_status": r.status_code, "text": r.text})
    except Exception as e:
        return False, {"error": str(e)}

# ---------- Page setup ----------
st.set_page_config(page_title="NeuroShield – Business Dashboard", layout="wide")

# ---------- CSS: dark cards + horizontal flow with glow (no wrap) ----------
st.markdown("""
<style>
.block-container {padding-top: 0.8rem; padding-bottom: 0.6rem;}
.h-title {font-size: 2.0rem; font-weight: 800; letter-spacing: .2px;}

:root {
  --card-bg: #0B0D12;
  --panel-bg: #0E1117;
  --border: rgba(255,255,255,0.06);
  --muted: rgba(200,205,215,0.75);
  --text: #E9EDF6;
  --idle: #64748B;
  --active: #60A5FA;
  --done: #22C55E;
}

.card { background: var(--card-bg); border: 1px solid var(--border);
        border-radius: 16px; padding: 18px; }

.metric { background: var(--card-bg); border: 1px solid var(--border);
          border-radius: 16px; padding: 16px 18px; margin-bottom: 14px; }
.metric h3 {margin: 0 0 6px 0; font-size: 1.05rem;}
.metric .score {font-weight: 800; font-size: 1.8rem; margin-right: 8px;}
.metric .sub {opacity: .8}

/* horizontal flow - fixed */
.flow-row { display:flex; align-items:stretch; gap:10px; flex-wrap:wrap;
            overflow-x:auto; white-space:no; padding-bottom:4px; }
.flow-pill { position:relative; padding:10px 14px; border-radius:12px;
             border:1px solid var(--border); background:#12151C; color:var(--text);
             font-weight:600; min-width:180px; text-align:center; }
.flow-arrow { color: var(--muted); font-size: 18px; align-self:center; margin:0 2px; }

/* badges & active glow */
.badge { position:absolute; top:-6px; right:-6px; width:12px; height:12px;
         border-radius:999px; border:2px solid #0B0D12; }
.badge.idle { background: var(--idle); opacity:.6; }
.badge.active { background: var(--active);
                box-shadow: 0 0 0 3px rgba(96,165,250,.18), 0 0 16px rgba(96,165,250,.35); }
.badge.done { background: var(--done); }
.flow-pill.active {
  box-shadow: 0 0 0 1px rgba(96,165,250,.35), 0 0 24px rgba(96,165,250,.20) inset,
              0 0 36px rgba(96,165,250,.25);
}
</style>
""", unsafe_allow_html=True)

# ---------- Helpers ----------
UI_STEPS = ["Sanitizer", "T0 Rules", "T1 Classifier", "Heavy Judge", "LangGraph", "Final Verdict"]

def trace_to_ui(trace:list[str]) -> list[str]:
    """Map backend trace to our UI step names."""
    t = trace or []
    steps = []
    if "sanitizer" in t: steps.append("Sanitizer")
    if "t0" in t: steps.append("T0 Rules")
    if "t1" in t: steps.append("T1 Classifier")
    if "heavy_judge" in t: steps.append("Heavy Judge")
    if "graph.llm" in t or "graph.verify" in t or "guardian" in t: steps.append("LangGraph")
    steps.append("Final Verdict")
    return steps

def render_flow(active_idx:int|None, steps:list[str], placeholder=None):
    pieces = ['<div class="card"><div style="font-weight:700; margin-bottom:8px;">Security Pipeline</div>',
              '<div class="flow-row">']
    for i, name in enumerate(steps):
        state = ("idle" if active_idx is None else
                 ("done" if i < active_idx else "active" if i == active_idx else "idle"))
        active_class = " active" if state == "active" else ""
        pieces.append(
            f'<div class="flow-pill{active_class}">{name}<span class="badge {state}"></span></div>'
        )
        if i < len(steps) - 1:
            pieces.append('<div class="flow-arrow">→</div>')
    pieces.append("</div></div>")
    html = "".join(pieces)
    (placeholder or st).markdown(html, unsafe_allow_html=True)

def metric_card(title:str, score:str, subtitle:str):
    st.markdown(f"""
    <div class="metric">
        <h3>{title}</h3>
        <div style="display:flex;align-items:baseline;gap:8px;">
            <span class="score">{score}</span>
            <span class="sub">{subtitle}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---------- Title ----------
st.markdown("""
    <div style="margin: 5px 0 15px 0;">
        <h1 style="margin: 10px 0 0 0; font-size: 2.5rem; font-weight: 700; color: #f0f0f0;">
            NeuroShield
        </h1>
        <p style="margin: 4px 0 0 0; font-size: 1.1rem; color: #a0a0a0;">
            Multi-tier LLM firewall with transparent decision paths
        </p>
    </div>
""", unsafe_allow_html=True)

# ---------- Layout ----------
left, right = st.columns([0.60, 0.40], gap="large")

with left:
    flow_ph = st.empty()
    render_flow(active_idx=None, steps=UI_STEPS, placeholder=flow_ph)

with right:
    # lifetime (optional) – collapsible
    with st.expander("Lifetime snapshot (recent events)", expanded=False):
        okm, mm = api_get("/v1/metrics/summary")
        if okm:
            c1, c2 = st.columns(2)
            with c1: metric_card("Blocked (recent)", str(mm.get("blocked","—")), "From events log")
            with c2: metric_card("Recent p95", f"{mm.get('p95_latency_ms','—')} ms", "End-to-end")

st.markdown("---")

# -------- Input area --------
mode = st.toggle("Paste LLM response", value=False)
if mode:
    prompt = st.text_area("Original Prompt", height=100, placeholder="Paste or type the original user prompt…")
    pasted = st.text_area("LLM Response", height=160, placeholder="Paste the model output here…")
else:
    prompt = st.text_area("Enter your prompt", height=140, placeholder="Describe your request or question for the model…")
    pasted = ""

analyze = st.button("Analyze Security", type="primary", use_container_width=True)

# -------- Action --------
if analyze:
    if not prompt.strip():
        st.warning("Please enter a prompt.")
        st.stop()

    payload = {"prompt": prompt}
    if mode:
        if not pasted.strip():
            st.warning("Please paste a model response.")
            st.stop()
        payload["pasted_llm_response"] = pasted

    t0 = time.time()
    ok, res = api_post("/v1/watchman/check", payload)
    t1 = time.time()

    if not ok:
        st.error(f"Gateway error: {res}")
        st.stop()

    # flow rendering (complete state)
    ui_flow = trace_to_ui(res.get("trace", []))
    render_flow(active_idx=len(ui_flow)-1, steps=ui_flow, placeholder=flow_ph)

    # ---- This run cards
    latency_ms = res.get("latency_ms")
    if isinstance(latency_ms, int):
        use_ms = latency_ms
    else:
        use_ms = int((t1 - t0) * 1000)

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Analysis Time", f"{use_ms} ms", "Server-measured")
    with c2: metric_card("Decision", str(res.get("decision","—")), "Gateway action")
    with c3: metric_card("Risk", f"{(res.get('risk_score') or 0.0)*100:.0f}%", "Composite risk")
    with c4: metric_card("Model Call", "Skipped (fast-path)" if not res.get("model_called") else "Yes", "LLM cost control")

    st.caption("Path: " + " → ".join(res.get("trace", [])))

    # ---- Reasons & scores (business-readable)
    st.markdown("### Reasons")
    reasons = res.get("reasons") or []
    if isinstance(reasons, list) and reasons:
        st.write("\n".join([f"• {r}" for r in reasons]))
    else:
        st.write("—")

    # T1 details
    t1s = (res.get("t1") or {}).get("scores") or {}
    cols = st.columns(4)
    cols[0].metric("Injection", f"{t1s.get('injection',0):.3f}")
    cols[1].metric("Jailbreak", f"{t1s.get('jailbreak',0):.3f}")
    cols[2].metric("LLM-Jack", f"{t1s.get('llm_jack',0):.3f}")
    cols[3].metric("Shadow-AI", f"{t1s.get('shadow_ai',0):.3f}")

    # ---- Final prompt / response / safety
    st.markdown("### Final Prompt")
    st.code(res.get("final_prompt") or "", language="markdown")

    if mode:
        st.markdown("### Safety Analysis (egress)")
    else:
        st.markdown("### LLM Response & Safety")
    safety = res.get("safety") or {}
    label = safety.get("label","safe")
    st.write(f"Safety label: **{label.upper()}**")
    llm_resp = res.get("llm_response") or ""
    st.text_area("LLM Response", value=llm_resp, height=160)

    # ---- Technical JSON (collapsible)
    with st.expander("Technical details (raw JSON)"):
        st.json(res)
