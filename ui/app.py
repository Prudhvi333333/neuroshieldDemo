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

def get_policy_info():
    """Get policy version and configuration from backend."""
    try:
        # Import here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from policy.loader import get_policy_version, load_policy
        
        version = get_policy_version()
        policy = load_policy()
        
        return {
            "version": version,
            "limits": policy.get("limits", {}),
            "thresholds": policy.get("thresholds", {})
        }
    except Exception as e:
        return {
            "version": "error",
            "limits": {},
            "thresholds": {},
            "error": str(e)
        }

def api_post(path, payload):
    try:
        r = requests.post(f"{BACKEND}{path}", headers={"Content-Type":"application/json", **_auth_header()}, json=payload, timeout=60)
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
AGENT_STEPS = ["InitialAnalysis", "SafeRewrite", "ModelCall", "ResponseVerifier", "CodeValidation", "RetrievalVerifier", "Audit"]

def trace_to_agent_flow(trace:list[str]) -> list[str]:
    """Map backend trace to agent flow step names."""
    t = trace or []
    steps = []
    if "sanitizer" in t or "initial" in t: steps.append("InitialAnalysis")
    if "rewrite" in t or "safe" in t: steps.append("SafeRewrite")
    if "graph.llm" in t or "model" in t: steps.append("ModelCall")
    if "verify" in t or "response" in t: steps.append("ResponseVerifier")
    if "code" in t or "validation" in t: steps.append("CodeValidation")
    if "retrieval" in t or "claim" in t: steps.append("RetrievalVerifier")
    steps.append("Audit")
    return steps

def render_agent_flow(active_idx:int|None, steps:list[str], placeholder=None):
    pieces = ['<div class="card"><div style="font-weight:700; margin-bottom:8px;">Agent Flow Pipeline</div>',
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

def decision_banner(decision:str, risk_pct:float, tenant:str, policy_version:str):
    """Render decision banner with key information."""
    decision_color = {
        "ALLOW": "#22C55E",
        "REWRITE": "#F59E0B", 
        "BLOCK": "#EF4444",
        "DENY": "#EF4444"
    }.get(decision.upper(), "#64748B")
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {decision_color}15, {decision_color}05);
                border: 1px solid {decision_color}40; border-radius: 12px; padding: 16px 20px;
                margin: 16px 0; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 16px;">
            <div style="font-size: 1.4rem; font-weight: 800; color: {decision_color};">{decision.upper()}</div>
            <div style="font-size: 1.2rem; font-weight: 600; color: #E9EDF6;">{risk_pct:.1f}% Risk</div>
        </div>
        <div style="text-align: right; color: var(--muted);">
            <div>Tenant: <strong>{tenant}</strong></div>
            <div>Policy: <strong>v{policy_version}</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def ids_badge(ids_data: dict, simulate_anomaly: bool = False):
    """Render IDS anomaly detection badge."""
    if simulate_anomaly:
        # Demo mode: force anomaly
        anomalous = True
        transition = "Rewrite→ShellTool"
        badge_color = "#EF4444"
        badge_text = "🚨 IDS: anomalous"
        detail_text = f"({transition})"
    else:
        # Real IDS data
        anomalous = ids_data.get("anomalous", False)
        transition = ids_data.get("transition")
        
        if anomalous:
            badge_color = "#EF4444"
            badge_text = "🚨 IDS: anomalous"
            detail_text = f"({transition})" if transition else ""
        else:
            badge_color = "#22C55E"
            badge_text = "✅ IDS: normal"
            detail_text = ""
    
    st.markdown(f"""
    <div style="
        display: inline-block;
        background: {badge_color};
        color: white;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 4px 0;
    ">
        {badge_text} {detail_text}
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

# IDS Anomaly Simulation Toggle (global scope)
with st.expander("🔧 IDS Demo Controls", expanded=False):
    simulate_ids_anomaly = st.checkbox(
        "Simulate IDS Anomaly", 
        value=False,
        help="Force IDS to show anomalous transition for demo purposes"
    )

# ---------- Layout ----------
left, right = st.columns([0.60, 0.40], gap="large")

with left:
    flow_ph = st.empty()
    render_agent_flow(active_idx=None, steps=AGENT_STEPS, placeholder=flow_ph)

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

    # Decision banner
    risk_score = res.get("risk_score", 0.0)
    risk_pct = (risk_score * 100) if risk_score is not None else 0.0
    decision_banner(
        decision=res.get("decision", "UNKNOWN"),
        risk_pct=risk_pct,
        tenant=res.get("tenant_id", "default"),
        policy_version=res.get("policy_version", "1.0")
    )
    
    # IDS Badge - show anomaly detection status
    ids_data = res.get("ids", {})
    if ids_data or simulate_ids_anomaly:
        ids_badge(ids_data, simulate_anomaly=simulate_ids_anomaly)
    
    # Agent flow rendering (complete state)
    agent_flow = trace_to_agent_flow(res.get("trace", []))
    render_agent_flow(active_idx=len(agent_flow)-1, steps=agent_flow, placeholder=flow_ph)

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

    st.caption("Execution Path: " + " → ".join(res.get("trace", [])))
    
    # Evidence Panels Section
    st.markdown("---")
    st.markdown("## 🔍 Evidence Panels")
    
    # Create evidence panel tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["T0/T1 Detection", "AFC Decisions", "IDS Analysis", "Code Validation", "Claim Verification"])
    
    with tab1:
        st.markdown("### T0/T1 Regex & DLP Hits")
        t0_data = res.get("t0") if res.get("t0") is not None else {}
        t1_data = res.get("t1") or {}
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**T0 Rules (Regex)**")
            t0_hits = t0_data.get("hits", []) if isinstance(t0_data, dict) else []
            if t0_hits:
                for hit in t0_hits:
                    st.write(f"• {hit.get('rule_name', 'Unknown rule')}")
            else:
                st.write("No T0 rule violations detected")
                
        with col2:
            st.markdown("**T1 Classifier (DLP)**")
            t1_scores = t1_data.get("scores", {}) if isinstance(t1_data, dict) else {}
            if t1_scores:
                for category, score in t1_scores.items():
                    if score > 0.1:  # Only show significant scores
                        st.write(f"• {category.title()}: {score:.3f}")
            else:
                st.write("No T1 classification triggers")
    
    with tab2:
        st.markdown("### AFC (Adaptive Flow Control) Decisions")
        afc_data = res.get("afc", [])
        
        if isinstance(afc_data, list) and afc_data:
            for i, tool_decision in enumerate(afc_data):
                if isinstance(tool_decision, dict):
                    tool_name = tool_decision.get("tool", f"Tool {i+1}")
                    schema_ok = tool_decision.get("schema_ok", True)
                    domain_ok = tool_decision.get("domain_ok", True)
                    cooldown_ok = tool_decision.get("cooldown_ok", True)
                    reasons = tool_decision.get("reasons", [])
                    
                    # Overall status
                    all_ok = schema_ok and domain_ok and cooldown_ok
                    status_color = "🟢" if all_ok else "🔴"
                    
                    st.markdown(f"**{status_color} {tool_name}**")
                    
                    # Status chips in columns
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        schema_chip = "🟢 Schema OK" if schema_ok else "🔴 Schema Failed"
                        st.write(schema_chip)
                    with col2:
                        domain_chip = "🟢 Domain OK" if domain_ok else "🔴 Domain Blocked"
                        st.write(domain_chip)
                    with col3:
                        cooldown_chip = "🟢 Cooldown OK" if cooldown_ok else "🔴 Cooldown Active"
                        st.write(cooldown_chip)
                    
                    # Show reasons if any
                    if reasons:
                        st.markdown("**Reasons:**")
                        for reason in reasons:
                            st.write(f"• {reason}")
                    
                    if i < len(afc_data) - 1:
                        st.markdown("---")
        else:
            st.write("No AFC tool decisions recorded")
    
    with tab3:
        st.markdown("### IDS (Intrusion Detection) Analysis")
        ids_data = res.get("ids", {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Transition State**")
            transition = ids_data.get("transition", "normal")
            st.write(f"State: `{transition}`")
            
        with col2:
            st.markdown("**Anomaly Detection**")
            anomaly = ids_data.get("anomaly_detected", False)
            anomaly_note = ids_data.get("anomaly_note", "No anomalies detected")
            st.write(f"Anomaly: {'⚠️ Yes' if anomaly else '✅ No'}")
            st.write(f"Note: {anomaly_note}")
    
    with tab4:
        st.markdown("### Code Validation Results")
        code_data = res.get("code_validation", {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Syntax Check**")
            syntax_ok = code_data.get("syntax_ok", True)
            st.write(f"Syntax: {'✅ Valid' if syntax_ok else '❌ Invalid'}")
            
        with col2:
            st.markdown("**Validation Errors**")
            errors = code_data.get("errors", [])
            if errors:
                for error in errors:
                    st.write(f"• {error}")
            else:
                st.write("No validation errors")
    
    with tab5:
        st.markdown("### Claim Verification")
        claims_data = res.get("claim_verification", {})
        claims = claims_data.get("claims", [])
        
        if claims:
            # Create a table for claims
            import pandas as pd
            df_data = []
            for claim in claims:
                df_data.append({
                    "Claim": claim.get("statement", "N/A"),
                    "Verdict": claim.get("verdict", "UNKNOWN"),
                    "Evidence Doc": claim.get("evidence_doc", "N/A")
                })
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No claims to verify")
    
    # Download Incident Report Button
    st.markdown("---")
    if st.button("📥 Download Incident Report", type="secondary", use_container_width=True):
        # Generate comprehensive markdown report
        report_lines = [
            f"# NeuroShield Incident Report",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Analysis Time:** {use_ms} ms",
            f"",
            f"## Decision Summary",
            f"- **Decision:** {res.get('decision', 'UNKNOWN')}",
            f"- **Risk Score:** {(res.get('risk_score', 0.0) * 100):.1f}%",
            f"- **Tenant:** {res.get('tenant_id', 'default')}",
            f"- **Policy Version:** {res.get('policy_version', '1.0')}",
            f"",
            f"## Agent Flow",
            f"Path: {' → '.join(agent_flow)}",
            f"Trace: {' → '.join(res.get('trace', []))}",
            f"",
            f"## Evidence Summary",
        ]
        
        # Add T0/T1 evidence
        if t0_data.get("hits"):
            report_lines.extend([
                f"### T0 Rule Violations",
                *[f"- {hit.get('rule_name', 'Unknown')}" for hit in t0_data["hits"]]
            ])
        
        if t1_data.get("scores"):
            report_lines.extend([
                f"### T1 Classification Scores",
                *[f"- {k.title()}: {v:.3f}" for k, v in t1_data["scores"].items() if v > 0.1]
            ])
        
        # Add reasons
        if reasons:
            report_lines.extend([
                f"",
                f"## Reasons",
                *[f"- {r}" for r in reasons]
            ])
        
        # Add final prompt and response
        report_lines.extend([
            f"",
            f"## Final Prompt",
            f"```",
            res.get("final_prompt", ""),
            f"```",
            f"",
            f"## LLM Response",
            f"```",
            res.get("llm_response", ""),
            f"```"
        ])
        
        report_content = "\n".join(report_lines)
        
        st.download_button(
            label="📄 Download Report",
            data=report_content,
            file_name=f"neuroshield_incident_{int(time.time())}.md",
            mime="text/markdown"
        )

    # ---- Performance Metrics Dashboard
    st.markdown("### Performance Metrics")
    
    # Fetch metrics from backend
    metrics_ok, metrics_data = api_get("/metrics/json")
    if metrics_ok and metrics_data.get("status") == "success":
        metrics = metrics_data.get("metrics", {})
        timing = metrics.get("timing", {})
        paths = metrics.get("paths", {})
        
        # Stage-0 and Stage-2 Performance Cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            stage0_total = timing.get("stage0.total", {})
            p50 = stage0_total.get("p50", 0)
            p95 = stage0_total.get("p95", 0)
            metric_card("Stage-0 Total", f"{p50:.1f}ms", f"p95: {p95:.1f}ms")
        
        with col2:
            stage2_total = timing.get("stage2.total", {})
            p50 = stage2_total.get("p50", 0)
            p95 = stage2_total.get("p95", 0)
            metric_card("Stage-2 Total", f"{p50:.1f}ms", f"p95: {p95:.1f}ms")
        
        with col3:
            stage0_afc = timing.get("stage0.afc", {})
            p50 = stage0_afc.get("p50", 0)
            p95 = stage0_afc.get("p95", 0)
            metric_card("AFC Checks", f"{p50:.1f}ms", f"p95: {p95:.1f}ms")
        
        with col4:
            total_requests = sum(paths.values()) if paths else 0
            most_common_path = max(paths.items(), key=lambda x: x[1]) if paths else ("none", 0)
            metric_card("Total Requests", str(total_requests), f"Top: {most_common_path[0]}")
        
        # Path Mix Statistics
        if paths:
            st.markdown("#### Path Mix Distribution")
            path_cols = st.columns(min(len(paths), 5))
            for i, (path, count) in enumerate(sorted(paths.items(), key=lambda x: x[1], reverse=True)[:5]):
                with path_cols[i]:
                    percentage = (count / total_requests * 100) if total_requests > 0 else 0
                    st.metric(path.replace("_", " ").title(), f"{count}", f"{percentage:.1f}%")
    else:
        st.warning("⚠️ Could not fetch performance metrics from backend")
    
    # ---- Quick Summary (business-readable)
    st.markdown("### Quick Summary")
    reasons = res.get("reasons") or []
    if isinstance(reasons, list) and reasons:
        st.write("\n".join([f"• {r}" for r in reasons]))
    else:
        st.write("No specific reasons provided")

    # T1 details (compact view)
    t1s = (res.get("t1") or {}).get("scores") or {}
    if any(score > 0.1 for score in t1s.values()):
        st.markdown("**T1 Risk Scores:**")
        cols = st.columns(4)
        cols[0].metric("Injection", f"{t1s.get('injection',0):.3f}")
        cols[1].metric("Jailbreak", f"{t1s.get('jailbreak',0):.3f}")
        cols[2].metric("LLM-Jack", f"{t1s.get('llm_jack',0):.3f}")
        cols[3].metric("Shadow-AI", f"{t1s.get('shadow_ai',0):.3f}")

    # ---- Final prompt / response / safety
    st.markdown("### Final Prompt")
    final_prompt = res.get("final_prompt", "")
    if final_prompt:
        st.code(final_prompt, language="markdown")
    else:
        st.write("No final prompt available")

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

# ---------- Policy Footer ----------
st.markdown("---")
st.markdown("### Policy Configuration")

policy_info = get_policy_info()
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"**Policy Version:** `{policy_info['version']}`")
    limits = policy_info.get('limits', {})
    if limits:
        st.markdown("**Limits:**")
        st.markdown(f"• Fastpath Max Length: {limits.get('fastpath_max_len', 'N/A')}")
        st.markdown(f"• Max Prompt Length: {limits.get('max_prompt_len', 'N/A')}")

with col2:
    thresholds = policy_info.get('thresholds', {})
    if thresholds:
        st.markdown("**Thresholds:**")
        st.markdown(f"• Fastpath: {thresholds.get('fastpath', 'N/A')}")
        st.markdown(f"• T0 Block: {thresholds.get('t0_block', 'N/A')}")
        st.markdown(f"• Risk for Model: {thresholds.get('risk_for_model_classify', 'N/A')}")

with col3:
    # Policy reload button
    if st.button("🔄 Reload Policy"):
        reload_ok, reload_result = api_post("/policy/reload", {})
        if reload_ok and reload_result.get("success"):
            st.success("✅ Policy reloaded successfully")
            st.rerun()
        else:
            st.error(f"❌ Policy reload failed: {reload_result.get('error', 'Unknown error')}")
    
    if policy_info.get('error'):
        st.warning(f"⚠️ Policy error: {policy_info['error']}")
