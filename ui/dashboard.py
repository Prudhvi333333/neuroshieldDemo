"""Streamlit dashboard (v2)
Modern dark layout with:
1. Prompt + optional pasted LLM response inputs
2. Real-time agent flow column (auto-generated from LangGraph)
3. Performance tiles grid populated from incremental state
4. Footer "Generate Summary" download button

First cut – renders existing functionality; style/metrics wiring to follow.
"""
from __future__ import annotations

# Ensure project root is on PYTHONPATH when launched via `streamlit run ui/dashboard.py`
import sys, pathlib
ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import json, os, time
from typing import Dict, List, Any

import streamlit as st

from langgraph_core.firewall_graph import build_firewall_graph, FirewallState as State

# ----------------------------------------------------------------------------
# Helper render functions (defined first so they are in scope)
# ----------------------------------------------------------------------------
def _tile(col, title: str, main: str, sub: Any):
    with col:
        st.markdown(f"### {title}")
        st.markdown(f"**{main}**")
        if sub is not None:
            st.markdown(f"Confidence: {sub}")

def _render_tiles(ph, state: State):
    """Render the performance / verdict tiles grid."""
    with ph.container():
        st.subheader("Module Verdicts & Metrics")
        cols = st.columns(2)
        _tile(cols[0], "Verifier", state.get("verdict", "?"), state.get("confidence"))
        _tile(cols[1], "IDS", "Anomalous" if state.get("ids_anomaly") else "Normal", state.get("ids_prob"))
        if "code_verdict" in state:
            _tile(cols[0], "Code Scan", state["code_verdict"], None)
        if "hallucination_reason" in state:
            _tile(cols[1], "Hallucination", state.get("hallucination_reason", "None"), None)

def _render_flow(ph, labels: List[str], state: State):
    """Render vertical agent flow with tick for completed nodes."""
    with ph.container():
        st.subheader("Agent Flow")
        for lbl in labels:
            st.markdown(f"- ✅ **{lbl}**")

# ----------------------------------------------------------------------------
# Page config & CSS
# ----------------------------------------------------------------------------
st.set_page_config("NeuroShield", layout="wide", page_icon="🛡️")

_CSS_PATH = os.path.join(os.path.dirname(__file__), "styles", "dark.css")
if os.path.exists(_CSS_PATH):
    with open(_CSS_PATH, "r", encoding="utf-8") as _f:
        st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)

st.title("🛡️ NeuroShield – Security Dashboard")

# ----------------------------------------------------------------------------
# Input widgets
# ----------------------------------------------------------------------------

a_prompt = st.text_area("Prompt ▶", height=140, key="prompt_v2")
use_paste = st.toggle("Paste LLM response for verification", key="paste_toggle_v2")
a_llm_resp = st.text_area("LLM Response", height=140, key="llm_resp_v2") if use_paste else ""

analyze_disabled = not (a_prompt.strip() or (use_paste and a_llm_resp.strip()))

if "events_v2" not in st.session_state:
    st.session_state.events_v2: List[Dict[str, Any]] = []

if st.button("Analyze Security 🚀", disabled=analyze_disabled):
    st.session_state.events_v2 = []  # reset history
    graph = build_firewall_graph()
    init_state: State = {"user_prompt": a_prompt}
    if use_paste and a_llm_resp:
        init_state["llm_response"] = a_llm_resp

    left_col, right_col = st.columns([1, 2], gap="large")
    flow_placeholder = left_col.empty()
    tiles_placeholder = right_col.empty()

    # Build mapping of node -> human label on the fly
    _flow_labels = []

    # Execute graph streaming
    current_state: State = init_state.copy()
    start_ts = time.perf_counter()
    with st.spinner("Running pipeline..."):
        _iterator = graph.stream(init_state) if hasattr(graph, "stream") else graph(init_state)
        for ev in _iterator:
            if not isinstance(ev, dict) or not ev:
                continue
            node = ev.get("__node__") if "__node__" in ev and len(ev) == 1 else list(ev.keys())[0]
            payload = ev.get(node) if node != ev.get("__node__") else {}
            if payload is None:
                payload = {}
            current_state.update(payload)
            st.session_state.events_v2.append({"node": node, "payload": payload, "t": time.perf_counter() - start_ts})

            # Update UI each iteration
            _flow_labels.append(node) if node not in _flow_labels else None
            _render_flow(flow_placeholder, _flow_labels, current_state)
            _render_tiles(tiles_placeholder, current_state)

    elapsed = time.perf_counter() - start_ts
    st.success(f"Completed in {elapsed:.2f}s")

    # --- Summary download ---
    md_lines = [
        f"# NeuroShield Analysis Summary",
        f"**Elapsed:** {elapsed:.2f}s\n",
        "## Verdicts",
        f"* Verifier: **{current_state.get('verdict', '?')}** – {current_state.get('reason','')}",
        f"* IDS: {'Anomalous' if current_state.get('ids_anomaly') else 'Normal'} (p={current_state.get('ids_prob')})",
    ]
    if 'code_verdict' in current_state:
        md_lines.append(f"* Code Scan: **{current_state['code_verdict']}**")
    if 'hallucination_reason' in current_state:
        md_lines.append(f"* Hallucination: {current_state['hallucination_reason']}")
    md_str = "\n".join(md_lines)
    st.download_button("📥 Generate Summary", md_str, file_name="neuroshield_summary.md")
