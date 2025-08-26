"""NeuroShield Business Dashboard (Streamlit)
Run with:  streamlit run ui/app.py
"""
from __future__ import annotations
import json, sys, time
from typing import Any, Dict, Optional, List

import requests
import streamlit as st

# Optional histogram via Plotly; fallback to Altair if missing
try:
    import plotly.express as px
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="NeuroShield Dashboard",
    layout="wide",
    page_icon="🛡️",
)

st.title("🛡️ NeuroShield – Business Dashboard")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _badge(text: str, color: str = "blue"):
    """Render a pill badge using markdown (simple)."""
    st.markdown(
        f"<span style='display:inline-block;background:{color};color:white;"
        f"padding:4px 10px;border-radius:999px;font-weight:600;font-size:12px;'>"
        f"{text}</span>",
        unsafe_allow_html=True,
    )

@st.cache_data(ttl=5)
def get_json(endpoint: str) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=4)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

@st.cache_data(ttl=5)
def get_sentinel_report() -> Optional[Dict[str, Any]]:
    return get_json("/v1/sentinel/report")

@st.cache_data(ttl=5)
def get_metrics_summary() -> Optional[Dict[str, Any]]:
    return get_json("/v1/metrics/summary")

@st.cache_data(ttl=5)
def get_policy_version() -> Optional[str]:
    data = get_json("/v1/policy/version")
    if isinstance(data, dict):
        return str(data.get("version"))
    return None

# -----------------------------------------------------------------------------
# Prompt Check section
# -----------------------------------------------------------------------------

st.subheader("Prompt Check")

# -- inner tabs -------------------------------------------------------------
pre_tab, post_tab = st.tabs(["Pre-LLM", "Post-LLM"])

# helper to render the common result block so it appears in either tab

def _render_results(res: Dict[str, Any]):
    if not res:
        return
    decision = res.get("decision", "?")
    _badge(
        f"Decision: {decision}",
        {
            "Blocked": "#e63946",
            "BlockedOutput": "#e63946",
            "RewriteThenAnalyze": "#e9c46a",
            "Likely factual (fast-path)": "#2a9d8f",
        }.get(decision, "#457b9d"),
    )
    st.write("\n")
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        risk = res.get("risk_score")
        st.metric("Risk", f"{risk:.2f}" if isinstance(risk, (int, float)) else "—")
    with c2:
        st.markdown("**Reasons**")
        for r in res.get("reasons") or []:
            _badge(r, "#6c757d")
        # Tier-0 rule hits
        t0 = res.get("t0") or {}
        if t0.get("rules_hit"):
            st.markdown("**T0 rules hit**")
            for rule in t0["rules_hit"]:
                _badge(str(rule), "#ef476f")
    with c3:
        st.markdown("**T1 scores**")
        t1 = (res.get("t1") or {}).get("scores", {})
        if t1:
            for k, v in t1.items():
                st.progress(v, text=f"{k} {v:.2f}")
        else:
            st.write("—")
    # Guardian safety info
    if (s := res.get("safety")) and isinstance(s, dict):
        st.markdown("### Guardian Safety")
        st.write(f"Label: **{s.get('label','?')}**")
        if s.get("reasons"):
            st.markdown("**Reasons:**")
            for r in s["reasons"]:
                _badge(str(r), "#8d99ae")
        if s.get("text") is not None:
            st.markdown("**Redacted Text:**")
            st.code(s["text"], language="markdown")
    with st.expander("final_prompt"):
        st.code(res.get("final_prompt") or "", language="markdown")
    with st.expander("llm_response"):
        st.code(res.get("llm_response") or "", language="markdown")

# -- tab 1: pre-LLM ----------------------------------------------------------
with pre_tab:
    prompt_pre = st.text_area(
        "Prompt", key="prompt_pre", placeholder="Type a prompt…", height=120,
        value=st.session_state.get("prompt_pre", ""),
    )
    colA, _ = st.columns([1, 2])
    with colA:
        btn_pre = st.button("Analyse", key="btn_pre", use_container_width=True)
    res_pre: Optional[Dict[str, Any]] = None
    if btn_pre and prompt_pre.strip():
        with st.spinner("Analysing prompt…"):
            try:
                res_pre = requests.post(
                    f"{API_BASE}/v1/watchman/check",
                    json={"prompt": prompt_pre},
                    timeout=10,
                ).json()
            except Exception as e:
                st.error(f"Request failed: {e}")
    _render_results(res_pre)

# -- tab 2: post-LLM ---------------------------------------------------------
with post_tab:
    prompt_post = st.text_area(
        "Prompt", key="prompt_post", placeholder="Type the SAME prompt…", height=120,
        value=st.session_state.get("prompt_pre", ""),
    )
    llm_resp_post = st.text_area(
        "LLM Response (optional)", key="llm_resp_post", placeholder="Paste response to verify…", height=120,
    )
    colB, _ = st.columns([1, 2])
    with colB:
        btn_post = st.button("Check Response", key="btn_post", use_container_width=True)
    res_post: Optional[Dict[str, Any]] = None
    if btn_post and prompt_post.strip():
        with st.spinner("Verifying response…"):
            payload = {"prompt": prompt_post, "pasted_llm_response": llm_resp_post}
            try:
                res_post = requests.post(
                    f"{API_BASE}/v1/watchman/check", json=payload, timeout=15
                ).json()
            except Exception as e:
                st.error(f"Request failed: {e}")
    _render_results(res_post)


st.divider()

# -----------------------------------------------------------------------------
# 2-column layout for Red-Team Quality & Pipeline Health (stack on mobile)
# -----------------------------------------------------------------------------

col1, col2 = st.columns(2, gap="large")

# --- Red-Team Quality ---------------------------------------------------------
with col1:
    st.subheader("Red-Team Quality")
    rep = get_sentinel_report()
    if rep:
        counts = rep.get("counts", {})
        precision = rep.get("precision", 0.0)
        recall = rep.get("recall", 0.0)
        fpr = rep.get("fpr", 0.0)
        st.metric("Precision", f"{precision:.2%}")
        st.metric("Recall", f"{recall:.2%}")
        st.metric("FPR", f"{fpr:.2%}")
        hist = rep.get("histogram")
        if hist:
            if _PLOTLY:
                bins = list(hist.keys())
                vals = list(hist.values())
                fig = px.bar(x=bins, y=vals, labels=dict(x="Risk bin", y="Count"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("Histogram:")
                st.json(hist)
        else:
            st.write("No histogram data.")
    else:
        st.info("No data yet.")

# --- Pipeline Health ----------------------------------------------------------
with col2:
    st.subheader("Pipeline Health")
    rep = get_sentinel_report()
    # default neutral
    def _card(title:str, value:Optional[float]):
        with st.container():
            st.markdown(f"**{title}**")
            if value is None:
                st.write("—")
            else:
                st.metric("Score", f"{value:.2%}")
    if not rep:
        _card("ContextAnalyzer", None)
        _card("RegexFilter", None)
        _card("RiskScorer", None)
        _card("FinalVerdict", None)
    else:
        runs: List[Dict[str, Any]] = rep.get("runs", [])
        attacks = [r for r in runs if r.get("kind") == "attacks"]
        benign  = [r for r in runs if r.get("kind") == "benign"]
        # ContextAnalyzer recall placeholder: using recall metric
        _card("ContextAnalyzer", rep.get("recall"))
        # RegexFilter precision on rule.block_regex
        t0_blocks = sum(1 for r in attacks if any("rule.block_regex" in (r.get("reasons") or []) for _ in [1]))
        regex_perf = t0_blocks/len(attacks) if attacks else None
        _card("RegexFilter", regex_perf)
        # RiskScorer separation metric
        try:
            avg_risk_att = sum(r.get("risk",0) for r in attacks)/len(attacks) if attacks else 0
            avg_risk_ben = sum(r.get("risk",0) for r in benign)/len(benign) if benign else 0
            rs = max(min(avg_risk_att - avg_risk_ben,1),0)
        except ZeroDivisionError:
            rs = None
        _card("RiskScorer", rs)
        # Final verdict precision
        _card("FinalVerdict", rep.get("precision"))

st.divider()

# -----------------------------------------------------------------------------
# Policy & SLO
# -----------------------------------------------------------------------------

st.subheader("Policy & SLO")
pol_ver = get_policy_version() or "—"
metrics = get_metrics_summary() or {}
p95 = metrics.get("p95_latency_ms")

st.markdown(f"**Policy version:** `{pol_ver}`")
if p95 is not None:
    st.metric("p95 latency (ms)", f"{p95:.0f}")
else:
    st.write("p95 latency: —")

st.caption("All data auto-refreshes every 5 s.")
