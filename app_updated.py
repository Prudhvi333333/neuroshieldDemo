from __future__ import annotations
import json, math, re, time
from pathlib import Path
import textwrap
from typing import Any, Dict
from collections import defaultdict
import datetime
import time  # Ensure time is imported
import html

import streamlit as st

# Standard library & third-party
import os

# Assuming these imports are correctly set up and accessible
from langgraph_core.firewall_graph import build_firewall_graph, State

import logging


logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Sanitize model/user text and render safely
def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    lines = (text or "").splitlines()
    cleaned = []
    for ln in lines:
        s = ln.strip()
        # Drop bare HTML tag lines that might have leaked
        if re.fullmatch(r"</?[a-zA-Z][^>]*>", s):
            continue
        # Drop our known container tags if they appear as lines
        if s.startswith(("<div", "</div", "<details", "</details")) and s.endswith(">"):
            continue
        cleaned.append(ln)
    text2 = "\n".join(cleaned).strip()
    # Remove trailing repeated closers
    text2 = re.sub(r"(</div>\s*)+$", "", text2, flags=re.IGNORECASE)
    # Remove HTML comments and any inline tags anywhere
    text2 = re.sub(r"<!--.*?-->", "", text2, flags=re.DOTALL)
    text2 = re.sub(r"</?(div|details|summary|section|span|pre|code|ul|li|strong|em|p|h[1-6]|br|hr)[^>]*>", "", text2, flags=re.IGNORECASE)
    # If any remaining generic tags exist, strip them too as a last resort
    text2 = re.sub(r"</?[^>]+>", "", text2)
    # Remove encoded tags like &lt;div ...&gt;
    text2 = re.sub(r"&lt;!--.*?--&gt;", "", text2, flags=re.DOTALL)
    text2 = re.sub(r"&lt;/?(div|details|summary|section|span|pre|code|ul|li|strong|em|p|h[1-6]|br|hr)[^&]*&gt;", "", text2, flags=re.IGNORECASE)
    text2 = re.sub(r"&lt;/?[^&]+?&gt;", "", text2)
    # Remove any of our UI-specific class mentions if they leaked as text
    text2 = re.sub(r"section-(card|title|content)|results-container", "", text2, flags=re.IGNORECASE)
    
    # Break Markdown code fences so they cannot swallow following HTML
    # Example: ```sql or ``` becomes `` + ZWSP + `, and ~~~ becomes ~~ + ZWSP + ~
    def _break_ticks(m: re.Match) -> str:
        s = m.group(0)
        return s[:2] + "\u200B" + s[2:]
    def _break_tildes(m: re.Match) -> str:
        s = m.group(0)
        return s[:2] + "\u200B" + s[2:]
    text2 = re.sub(r"`{3,}", _break_ticks, text2)
    text2 = re.sub(r"~{3,}", _break_tildes, text2)
    # Also neutralize horizontal-rule patterns that could create odd spacing
    # Use a function replacement so we can insert an actual zero-width space without bad escapes
    text2 = re.sub(
        r"^(\s*)([-*_]){3,}\s*$",
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(2)}\u200B{m.group(2)}",
        text2,
        flags=re.MULTILINE,
    )
    return text2

def _render_text_block(text: str) -> str:
    safe = _sanitize_text(text)
    # Return properly escaped text without HTML tags to avoid rendering issues
    return html.escape(safe)

# Strip leading indentation from multi-line HTML so Markdown doesn't treat lines as code blocks
def _strip_leading_spaces(html_str: str) -> str:
    return re.sub(r'^[ \t]+', '', html_str, flags=re.MULTILINE)

# Configure Streamlit runtime options early
try:
    st.set_option('server.fileWatcherType', 'poll')  # avoid cross-drive watchdog on Windows
except Exception:
    pass

# Custom CSS for dark theme
def load_dark_theme():
    st.markdown("""
    <style>
    /* Main app background */
    .stApp {
        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 50%, #3e3e5e 100%);
        color: #ffffff;
    }
    
    /* Header styling */
    .main-header {
        text-align: left;
        padding: 1rem 1.5rem 1.5rem 1.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        margin: 1rem 0 1rem 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.5rem;
        text-shadow: 0 0 20px rgba(116, 185, 255, 0.3);
        text-align: left;
    }
    
    .subtitle {
        font-size: 1.1rem;
        color: #b4b4c8;
        margin-bottom: 0;
        font-weight: 400;
        text-align: left;
    }
    
    /* Input section styling */
    .input-section {
        background: rgba(45, 45, 68, 0.8);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(5px);
    }
    
    .input-label {
        font-size: 1.2rem;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 0.5rem;
        display: block;
    }
    
    .input-description {
        font-size: 0.9rem;
        color: #9ca3af;
        margin-bottom: 1rem;
        display: block;
    }
    
    /* Text area styling */
    .stTextArea > div > div > textarea {
        background: rgba(62, 62, 94, 0.6) !important;
        border: 2px solid rgba(116, 185, 255, 0.3) !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-size: 1rem !important;
        padding: 1rem !important;
        backdrop-filter: blur(5px) !important;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #74b9ff !important;
        box-shadow: 0 0 0 2px rgba(116, 185, 255, 0.2) !important;
    }
    
    .stTextArea > div > div > textarea:disabled {
        background: rgba(45, 45, 68, 0.3) !important;
        border: 2px solid rgba(108, 114, 147, 0.3) !important;
        color: #6c7293 !important;
        cursor: not-allowed !important;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 2rem !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(116, 185, 255, 0.3) !important;
        width: 100% !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(116, 185, 255, 0.4) !important;
        background: linear-gradient(135deg, #0984e3 0%, #74b9ff 100%) !important;
    }
    
    .stButton > button:disabled {
        background: rgba(116, 185, 255, 0.3) !important;
        transform: none !important;
        box-shadow: none !important;
    }
    
    /* Toggle styling */
    .stCheckbox > label {
        color: #ffffff !important;
        font-size: 1rem !important;
    }
    
    /* Results container styling */
    .results-container {
        background: linear-gradient(135deg, rgba(30, 30, 46, 0.95) 0%, rgba(45, 45, 68, 0.9) 100%);
        border-radius: 16px;
        padding: 2.5rem;
        margin-top: 2rem;
        border: 1px solid rgba(116, 185, 255, 0.2);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
    }
    
    /* Removed analysis-header styles - no longer used */
    
    .top-metrics {
        display: flex;
        gap: 1.5rem;
        margin-bottom: 2.5rem;
    }
    
    .metric-card {
        flex: 1;
        background: transparent;
        padding: 2rem 1.5rem;
        border-radius: 14px;
        text-align: center;
        border: 1px solid rgba(116, 185, 255, 0.2);
        box-shadow: none;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(116, 185, 255, 0.3);
        border-color: rgba(116, 185, 255, 0.4);
    }
    
    .metric-title {
        font-size: 1rem;
        color: #b4b4c8;
        margin-bottom: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        color: #ffffff;
        text-shadow: 0 0 15px rgba(116, 185, 255, 0.4);
    }
    
    .metric-value.completed {
        font-weight: 700;
    }
    
    .section-card {
        background: linear-gradient(135deg, rgba(45, 45, 68, 0.9) 0%, rgba(62, 62, 94, 0.8) 100%);
        padding: 1.5rem;
        margin-bottom: 2.25rem;
        border-radius: 14px;
        border: 1px solid rgba(116, 185, 255, 0.2);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .section-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 30px rgba(116, 185, 255, 0.2);
        border-color: rgba(116, 185, 255, 0.3);
    }
    
    .section-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #74b9ff;
        margin-bottom: 0.6rem;
        padding-bottom: 0.6rem;
        border-bottom: 2px solid rgba(116, 185, 255, 0.3);
        text-shadow: 0 0 10px rgba(116, 185, 255, 0.3);
        position: relative;
    }
    
    .section-title::after {
        content: '';
        position: absolute;
        bottom: -2px;
        left: 0;
        width: 50px;
        height: 2px;
        background: linear-gradient(90deg, #74b9ff, #0984e3);
        border-radius: 1px;
    }
    
    .section-content {
        color: #ffffff;
        line-height: 1.6;
        font-size: 1.05rem;
        font-weight: 400;
        white-space: pre-wrap;
        margin: 0;
    }
    
    .safe-status {
        color: #00b894;
        font-weight: 600;
        text-shadow: 0 0 10px rgba(0, 184, 148, 0.4);
    }
    
    .threat-status {
        color: #e17055;
        font-weight: 600;
        text-shadow: 0 0 10px rgba(225, 112, 85, 0.4);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {display: none !important;}
    footer {display: none !important;}
    header {display: none !important;}
    
    /* Custom loading animation */
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(116, 185, 255, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(116, 185, 255, 0); }
        100% { box-shadow: 0 0 0 0 rgba(116, 185, 255, 0); }
    }
    
    /* Warning status styling */
    .warning-status {
        color: #fdcb6e;
        font-weight: 600;
        text-shadow: 0 0 10px rgba(253, 203, 110, 0.4);
    }
    
    .neutral-status {
        color: #74b9ff;
        font-weight: 600;
        text-shadow: 0 0 10px rgba(116, 185, 255, 0.4);
    }
    
    .pulse-animation {
        animation: pulse 2s infinite;
    }
    
    /* Ensure progress bar and status text are properly hidden */
    .stProgress > div > div > div > div {
        background: transparent !important;
    }
    
    .stProgress > div > div > div > div > div {
        background: linear-gradient(90deg, #74b9ff, #0984e3) !important;
    }
    
    /* Hide empty status text */
    .element-container:has(.stEmpty) {
        display: none !important;
    }
    
    /* Hide any residual HTML tags that might leak through */
    .section-content {
        font-family: inherit !important;
    }
    
    /* Ensure text content is properly displayed */
    .section-content {
        word-wrap: break-word;
        overflow-wrap: break-word;
    }

    /* Prevent stray empty blocks from rendering as dark bars */
    .results-container > div:empty {
        display: none !important;
        height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: 0 !important;
    }

    /* Ensure no pseudo elements overlay the metrics row */
    .top-metrics::before {
        content: none !important;
        display: none !important;
    }
    .top-metrics { margin-bottom: 1.8rem; }
    
    /* Ensure a small gap between consecutive cards */
    .section-card + .section-card { margin-top: 1.5rem; }
    /* Reduce bottom space after the last card on the page */
    .section-card:last-of-type { margin-bottom: 0.5rem; }
    </style>
    """, unsafe_allow_html=True)

# Set page config with dark theme
st.set_page_config(
    page_title="NeuroShield GenAI Security Platform",
    layout="wide",
    page_icon="🛡️",
    initial_sidebar_state="collapsed"
)

# Load dark theme
load_dark_theme()

# Main header
st.markdown('<div class="main-header"><h1 class="title">NeuroShield GenAI Security Platform 🛡️</h1><p class="subtitle">Multi-tier security with real-time analysis of LLM traffic</p></div>', unsafe_allow_html=True)

# Initialize session state for results
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = {}
if "analysis_complete" not in st.session_state:
    st.session_state.analysis_complete = False
if "current_step" not in st.session_state:
    st.session_state.current_step = 0

# Input section with plain text
# Use placeholders so we can render the toggle first (to get its value) while keeping visual order
prompt_label_html = '<span style="font-size: 1.1rem; font-weight: 700; color: #ffffff; margin-bottom: 0.5rem; display: block;">Enter your prompt:</span>'
st.markdown(prompt_label_html, unsafe_allow_html=True)
prompt_placeholder = st.empty()      # Reserve space for the prompt textarea (above)
toggle_placeholder = st.empty()      # Reserve space for the toggle (below the prompt)

# Render the toggle in its reserved place to capture its value
paste_toggle = toggle_placeholder.checkbox(
    "🔄 Paste LLM response",
    key="paste_toggle_firewall",
    help="Enable this to paste an existing LLM response for verification"
)

# Now render the prompt into its reserved spot, disabled when paste mode is ON
prompt = prompt_placeholder.text_area(
    "Enter your prompt",
    height=120,
    key="prompt",
    placeholder="Describe your request or question for the model...",
    label_visibility="collapsed",
    disabled=paste_toggle  # When paste toggle is ON, block the prompt box
)

pasted_llm_response = ""
if paste_toggle:
    st.markdown('<span style="font-size: 1.1rem; font-weight: 700; color: #ffffff; margin-bottom: 0.5rem; display: block;">Paste LLM Response:</span>', unsafe_allow_html=True)
    pasted_llm_response = st.text_area("LLM Response", height=120, key="pasted_llm_response_area", placeholder="Paste the LLM response here...")
else:
    # Clear the response when toggle is off
    if "pasted_llm_response_area" in st.session_state:
        st.session_state.pasted_llm_response_area = ""

# Initialize placeholders for sequential sections
section_placeholders = {
    "metrics": st.empty(),
    "classification": st.empty(),
    "reasoning": st.empty(),
    "safe_prompt": st.empty(),
    "llm_response": st.empty()
}

# Button logic
is_prompt_present = bool(prompt.strip()) and not paste_toggle
is_pasted_response_present = bool(pasted_llm_response.strip()) and paste_toggle
analyze_button_disabled = not (is_prompt_present or is_pasted_response_present)

# Analyze button with improved styling - full width
if st.button("🚀 Analyze Security", disabled=analyze_button_disabled, key="analyze_btn"):
    # Reset analysis state
    st.session_state.analysis_results = {}
    st.session_state.analysis_complete = False
    st.session_state.current_step = 0
    
    # Clear previous results
    for placeholder in section_placeholders.values():
        placeholder.empty()
    
    # Start analysis with optimized backend
    graph = build_firewall_graph()
    initial_graph_state: State = {
        "user_prompt": ("" if paste_toggle else prompt),
        "classification": "",
        "risk_score": 0.0,
        "reason": "",
        "attack_detection": {},
        "final_prompt": "",
        "llm_response": ""
    }
    if paste_toggle and pasted_llm_response:
        initial_graph_state["llm_response"] = pasted_llm_response
        # Skip verification for pasted responses - they are already the "response" to verify
        initial_graph_state["skip_verification"] = True

    start_time = time.perf_counter()
    
    try:
        current_accumulated_state: State = initial_graph_state.copy()
        
        # Create progress bar and initial tiles
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Show initial 3 tiles immediately
        initial_tiles = st.empty()
        initial_tiles.markdown(f'''
        <div class="top-metrics">
            <div class="metric-card">
                <div class="metric-title">Classification</div>
                <div class="metric-value">Analyzing...</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Risk Score</div>
                <div class="metric-value">0.000</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        status_text.text("🔍 Initializing security analysis...")
        progress_bar.progress(10)
        
        with st.spinner("🔍 Analyzing security..."):
            step_count = 0
            total_steps = 7  # Approximate number of analysis steps
            
            for event in graph.stream(initial_graph_state):
                if not isinstance(event, dict) or not event:
                    continue
                
                # Debug: Print each event to understand structure
                print(f"DEBUG UI Event: {event}")
                    
                step_count += 1
                progress = min(10 + (step_count / total_steps) * 80, 90)
                progress_bar.progress(int(progress))
                
                # Skip metadata-only events but update with actual data
                if "__node__" in event and len(event) == 1:
                    node_name = event["__node__"]
                    status_text.text(f"🔍 Processing: {node_name}")
                    continue
                
                # Extract nested data from graph events (CRITICAL FIX)
                for key, value in event.items():
                    if not key.startswith("__") and isinstance(value, dict):
                        # This is node data - extract the actual state values
                        current_accumulated_state.update(value)
                        status_text.text(f"🔍 Analyzing: {key}")
                        # Debug: Show what we're extracting
                        print(f"DEBUG UI Extract from {key}: Classification: {value.get('classification')}, Risk: {value.get('risk_score')}")
                        print(f"DEBUG UI State after update: Classification: {current_accumulated_state.get('classification')}, Risk: {current_accumulated_state.get('risk_score')}")
                    elif not key.startswith("__"):
                        # Direct key-value pair
                        current_accumulated_state[key] = value
        
        # Update initial tiles with final results
        initial_tiles.markdown(f'''
        <div class="top-metrics">
            <div class="metric-card">
                <div class="metric-title">Classification</div>
                <div class="metric-value">{current_accumulated_state.get("classification", "Unknown")}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Risk Score</div>
                <div class="metric-value">{current_accumulated_state.get("risk_score", 0.0):.3f}</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Complete progress
        progress_bar.progress(100)
        status_text.text("✅ Analysis completed!")
        
        # Store results for display with detailed timing
        analysis_time = time.perf_counter() - start_time
        
        # Debug: Print final accumulated state before storing
        print(f"DEBUG Final UI State: Classification={current_accumulated_state.get('classification')}, Risk={current_accumulated_state.get('risk_score')}, Reason={current_accumulated_state.get('reason')}")
        print(f"DEBUG All State Keys: {list(current_accumulated_state.keys())}")
        
        st.session_state.analysis_results = {
            "final_decision": current_accumulated_state.get("classification", "Unknown"),
            "risk_score": current_accumulated_state.get("risk_score", 0.0),
            "reason": current_accumulated_state.get("reason", "No analysis performed"),
            "attack_detection": current_accumulated_state.get("attack_detection", {}),
            "safe_prompt": current_accumulated_state.get("final_prompt", ""),
            "llm_response": current_accumulated_state.get("llm_response", ""),
            "bypass_used": current_accumulated_state.get("bypass_used", False),
            "classification_time": current_accumulated_state.get("classification_time", 0.0),
            "analysis_time": current_accumulated_state.get("analysis_time", 0.0),
            "rewrite_time": current_accumulated_state.get("rewrite_time", 0.0),
            "llm_time": current_accumulated_state.get("llm_time", 0.0),
            "verification_time": current_accumulated_state.get("verification_time", 0.0),
            "search_time": current_accumulated_state.get("search_time", 0.0),
            "response_verdict": current_accumulated_state.get("response_verdict", "Unknown"),
            "raw_verifier_output": current_accumulated_state.get("raw_verifier_output", ""),
            "corrected_llm_response": current_accumulated_state.get("corrected_llm_response", ""),
            "correction_time": current_accumulated_state.get("correction_time", 0.0),
            "final_llm_response": current_accumulated_state.get("final_llm_response", ""),
            "final_response_source": current_accumulated_state.get("final_response_source", ""),
            "final_response_time": current_accumulated_state.get("final_response_time", 0.0),
            "response_security": current_accumulated_state.get("response_security", {}),
            "response_security_time": current_accumulated_state.get("response_security_time", 0.0),
            "is_response_analysis": bool(paste_toggle and bool(pasted_llm_response.strip())),
            "input_mode": ("paste" if paste_toggle and pasted_llm_response.strip() else "prompt")
        }
        
        # Debug: Print what we're storing in session state
        print(f"DEBUG Session State: {st.session_state.analysis_results}")
        st.session_state.analysis_complete = True
        
        # Clear progress indicators before rerun
        progress_bar.empty()
        status_text.empty()
        initial_tiles.empty()  # Clear the initial tiles
        
        # Small delay to ensure UI updates
        time.sleep(0.1)
        
        # Force a rerun to update the UI
        st.rerun()
        
    except Exception as e:
        st.error(f"Analysis failed: {e}")

# Display results if analysis is complete
if st.session_state.analysis_complete and st.session_state.analysis_results:
    results = st.session_state.analysis_results
    
    # Compose entire results into a single container to avoid empty wrapper artifacts
    risk_score = results.get("risk_score", 0.0)
    bypass_text = "⚡ Fast" if results.get("bypass_used") else "🧠 Deep"
    
    # Ensure risk_score is a number
    if not isinstance(risk_score, (int, float)):
        risk_score = 0.0
    
    # Determine analysis mode based on stored results, not the current toggle
    is_response_analysis = bool(results.get("is_response_analysis", False))
    
    # Set classification based on analysis type
    if is_response_analysis:
        # For pasted responses, show factual accuracy (normalized)
        response_verdict = str(results.get("response_verdict", "Unknown")).strip()
        v_lc = response_verdict.lower()
        # Normalize
        if ("incorrect" in v_lc) or ("halluc" in v_lc):
            classification = "Factually incorrect"
            response_category = "incorrect"
        elif "partial" in v_lc:
            classification = "Partially correct"
            response_category = "partial"
        elif "correct" in v_lc:
            classification = "Factually correct"
            response_category = "correct"
        elif ("unverif" in v_lc) or ("unknown" in v_lc) or (not v_lc):
            classification = "Unverifiable"
            response_category = "unverifiable"
        else:
            classification = response_verdict
            response_category = "other"

        # If the final response came from a verified generation, upgrade Unknown/Unverifiable display to Factually correct
        final_src_norm = (results.get("final_response_source") or "").strip()
        if response_category in ("unverifiable", "other") and final_src_norm in (
            "generated_verified", "generated_verified_from_response", "pasted_verified",
        ):
            classification = "Factually correct"
            response_category = "correct"
    else:
        # For prompts, show the security classification
        classification = results.get("final_decision", "Unknown")
    
    # Prepare classification details based on analysis type
    if is_response_analysis:
        # For pasted LLM responses, show factual accuracy (normalized)
        if response_category == "correct":
            classification_text = f'<span class="safe-status">✅ Response Verification:</span> Content is factually accurate'
        elif response_category == "partial":
            classification_text = f'<span class="warning-status">⚠️ Response Verification:</span> Content has minor inaccuracies or missing details'
        elif response_category == "incorrect":
            classification_text = f'<span class="threat-status">❌ Response Verification:</span> Content contains factual errors or hallucinations'
        elif response_category == "unverifiable":
            classification_text = f'<span class="neutral-status">❓ Response Verification:</span> Content cannot be verified with available sources'
        else:
            classification_text = f'<span class="neutral-status">🔍 Response Verification:</span> {classification}'
    else:
        # For prompt analysis, drive banner primarily from classification/risk, and enrich with attack types
        attack_types = []
        if results.get("attack_detection"):
            for attack_type, details in results["attack_detection"].items():
                if isinstance(details, dict) and details.get("detected"):
                    attack_types.append(attack_type.replace("_", " ").title())

        cls = str(results.get("final_decision", "Unknown") or "Unknown")
        rs = float(results.get("risk_score", 0.0) or 0.0)
        reason = html.escape(str(results.get("reason", "")))
        is_blocked = (cls == "Blocked") or (results.get("final_prompt") == "[BLOCKED]") or (rs >= 0.85)
        is_risky = (cls == "Risky") or (0.6 <= rs < 0.85)

        if is_blocked:
            prefix = '<span class="threat-status">⛔ Blocked:</span>'
            extra = f" Reason: {reason}" if reason else ""
            threats = f" Threats: {', '.join(attack_types)}" if attack_types else ""
            classification_text = f"{prefix}{extra}{threats}"
        elif is_risky:
            prefix = '<span class="warning-status">⚠️ Risky:</span>'
            extra = f" Reason: {reason}" if reason else ""
            threats = f" Threats: {', '.join(attack_types)}" if attack_types else ""
            classification_text = f"{prefix}{extra}{threats}"
        else:
            # Safe/default
            if attack_types:
                classification_text = f"<span class=\"neutral-status\">🔍 Observations:</span> {', '.join(attack_types)}"
            else:
                classification_text = f'<span class="safe-status">✅ Security Analysis Complete:</span> Content passed all security checks successfully'
    
    # Timing breakdown (currently for future use)
    timing_breakdown = []
    if results.get("rewrite_time", 0) > 0:
        timing_breakdown.append(f"Rewrite: {results['rewrite_time']:.2f}s")
    if results.get("llm_time", 0) > 0:
        timing_breakdown.append(f"LLM: {results['llm_time']:.2f}s")
    if results.get("verification_time", 0) > 0:
        timing_breakdown.append(f"Verification: {results['verification_time']:.2f}s")
    if results.get("search_time", 0) > 0:
        timing_breakdown.append(f"Search: {results['search_time']:.2f}s")
    
    timing_text = " | ".join(timing_breakdown) if timing_breakdown else "Fast bypass used"

    # Top metrics
    # Build timing cards dynamically based on analysis type
    if is_response_analysis:
        # Response verification classification time and response risk calc time
        vt = float(results.get("verification_time", 0.0) or 0.0)
        rst = float(results.get("response_security_time", 0.0) or 0.0)
        vt_disp = (f"{vt*1000:.0f}ms" if vt < 1.0 else f"{vt:.2f}s")
        rst_disp = (f"{rst*1000:.0f}ms" if rst < 1.0 else f"{rst:.2f}s")
        extra_cards_html = f'''
            <div class="metric-card">
                <div class="metric-title">Verification Time</div>
                <div class="metric-value">{vt_disp}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Response Risk Time</div>
                <div class="metric-value">{rst_disp}</div>
            </div>
        '''
    else:
        # Prompt classification + risk decision time
        ct = float(results.get("classification_time", 0.0) or 0.0)
        ct_disp = (f"{ct*1000:.0f}ms" if ct < 1.0 else f"{ct:.2f}s")
        extra_cards_html = f'''
            <div class="metric-card">
                <div class="metric-title">Decision Time</div>
                <div class="metric-value">{ct_disp}</div>
            </div>
        '''

    st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="top-metrics">
        <div class="metric-card">
            <div class="metric-title">Analysis Status</div>
            <div class="metric-value completed">Completed</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">{"Verification" if is_response_analysis else "Classification"}</div>
            <div class="metric-value">{classification}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Risk Score</div>
            <div class="metric-value">{risk_score:.3f}</div>
        </div>
        {extra_cards_html}
    </div>''')), unsafe_allow_html=True)

    # Classification card
    st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
        <div class="section-title">🔍 Security Classification</div>
        <div class="section-content">{classification_text}</div>
    </div>''')), unsafe_allow_html=True)

    # Reasoning card
    reasoning_title = "🔍 Verification Analysis" if is_response_analysis else "🧠 Security Reasoning"
    reason_text = (results.get("raw_verifier_output", "") if (is_response_analysis and results.get("raw_verifier_output", "")) else results.get('reason', ''))
    if is_response_analysis and not reason_text:
        reason_text = 'Response analyzed for factual accuracy'
    st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
        <div class="section-title">{reasoning_title}</div>
        <div class="section-content">
            <div><strong>Verdict:</strong> {html.escape(classification)}</div>
            <div style="margin-top:0.25rem;">{_render_text_block(reason_text)}</div>
        </div>
    </div>''')), unsafe_allow_html=True)

    # Response-level security check
    sec = results.get("response_security") or {}
    if sec:
        sec_cls = str(sec.get("classification", "Safe"))
        sec_risk = float(sec.get("risk_score", 0.0) or 0.0)
        sec_reason = str(sec.get("reason", "No security risks detected"))
        sec_time = float(results.get("response_security_time", 0.0) or 0.0)
        det = sec.get("adversarial_detections") or {}
        det_count = int(sec.get("detection_count", len(det)))

        badge = (
            '<span class="threat-status">🚨 Blocked</span>' if sec_cls == "Blocked" else
            '<span class="warning-status">⚠️ Risky</span>' if sec_cls == "Risky" else
            '<span class="safe-status">✅ Safe</span>'
        )

        # Friendlier labels and short explanations for non-experts
        label_map = {
            "statistical_anomalies": "Formatting irregularities",
            "encoding": "Encoded content detected",
            "obfuscation": "Obfuscation indicators",
            "context_manipulation": "Context manipulation phrasing",
            "social_engineering": "Social engineering language"
        }
        explain_map = {
            "statistical_anomalies": "The text has small formatting quirks (e.g., punctuation/length mix). This is common in lists and is low risk.",
            "encoding": "Contains long encoded strings (like base64). Could hide instructions.",
            "obfuscation": "Uses techniques that can hide intent (e.g., 'translate', 'decode').",
            "context_manipulation": "Story/roleplay wording that may try to shift guardrails.",
            "social_engineering": "Urgent/persuasive phrasing that could pressure actions."
        }

        # Build friendly summary
        if sec_cls == "Safe" and (det_count == 0 or sec_risk < 0.1):
            friendly_reason = "No security threats detected."
            if det_count > 0:
                friendly_reason += " Minor pattern noted (low risk)."
        elif sec_cls == "Risky":
            friendly_reason = "Potentially risky patterns detected. Review advised."
        else:
            friendly_reason = sec_reason or "Security assessment provided."

        det_lines = []
        if det_count > 0:
            for k, v in det.items():
                if not v:
                    continue
                label = label_map.get(k, k.replace("_", " ").title())
                extras = []
                if isinstance(v, dict):
                    if "count" in v and v["count"]:
                        extras.append(f"x{v['count']}")
                    hint = explain_map.get(k)
                    if hint:
                        extras.append(hint)
                suffix = f" – {' '.join(extras)}" if extras else ""
                det_lines.append(f"• {label}{suffix}")
        det_text = "\n".join(det_lines)

        st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
            <div class="section-title">🛡️ Response Security Check{' (%.2fs)' % sec_time if sec_time else ''}</div>
            <div class="section-content">
                <div><strong>Status:</strong> {badge} <span style="margin-left:0.5rem; color:#9ca3af;">(risk {sec_risk:.2f})</span></div>
                <div style="margin-top:0.25rem;">{_render_text_block(friendly_reason)}</div>
                {(_render_text_block(det_text) if det_text else '')}
            </div>
        </div>''')), unsafe_allow_html=True)

    # Rewrite section (conditional)
    if results["safe_prompt"] and results["safe_prompt"] != prompt:
        rewrite_time_text = f" (Generated in {results.get('rewrite_time', 0):.2f}s)" if results.get('rewrite_time', 0) > 0 else ""
        safe_prompt_display_raw = results["safe_prompt"] if results["safe_prompt"] != "[BLOCKED]" else "⛔ Blocked."
        safe_prompt_display = _render_text_block(safe_prompt_display_raw)
        st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
            <div class="section-title">🔄 Rewritten Safe Prompt{rewrite_time_text}</div>
            <div class="section-content">{safe_prompt_display}</div>
        </div>''')), unsafe_allow_html=True)

    # LLM response section (conditional)
    if results.get("llm_response") or results.get("final_llm_response"):
        llm_time_text = f" (Generated in {results.get('llm_time', 0):.2f}s)" if results.get('llm_time', 0) > 0 else ""
        
        if is_response_analysis:
            # Prefer the graph-produced final_llm_response (verified/corrected/best-effort)
            final_resp = (results.get("final_llm_response") or "").strip()
            final_src = (results.get("final_response_source") or "").strip()
            corrected = (results.get("corrected_llm_response") or "").strip()
            if final_resp:
                title_map = {
                    "corrected": "🛠️ Corrected Final Response (Verified)",
                    "generated_verified": "✅ Verified Final Response",
                    "generated_verified_from_response": "✅ Verified Final Response",
                    "generated_unverifiable": "ℹ️ Best-Effort Final Response",
                    "generated_unverifiable_from_response": "ℹ️ Best-Effort Final Response",
                    "pasted": "🤖 Final Response",
                    "pasted_verified": "✅ Verified Final Response",
                    "pasted_unverifiable": "ℹ️ Best-Effort Final Response"
                }
                title = title_map.get(final_src, "🤖 Final Response")
                meta = []
                if final_src == "corrected" and results.get("correction_time", 0):
                    meta.append(f"<strong>Correction Time:</strong> {results['correction_time']:.2f}s")
                if results.get("final_response_time", 0):
                    meta.append(f"<strong>Final:</strong> {results['final_response_time']:.2f}s")
                meta_html = ("<div style=\"margin-top: 0.75rem; font-size: 0.9rem; color: #6c7293;\">" + " ".join(meta) + "</div>") if meta else ""
                st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
                    <div class="section-title">{title}</div>
                    <div class="section-content">{_render_text_block(final_resp)}</div>
                    {meta_html}
                </div>''')), unsafe_allow_html=True)
                # (Removed) Original Pasted Response block to prevent confusion and layout issues
            else:
                # Fallback to corrected or pasted as before
                if response_category in ("incorrect", "partial") and corrected:
                    corr_time = results.get("correction_time", 0.0)
                    st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
                        <div class="section-title">🛠️ Corrected Response (Verified)</div>
                        <div class="section-content">{_render_text_block(corrected)}</div>
                        <div style="margin-top: 0.75rem; font-size: 0.9rem; color: #6c7293;">
                            <strong>Correction Time:</strong> {corr_time:.2f}s
                        </div>
                    </div>''')), unsafe_allow_html=True)
                    st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
                        <div class="section-title">📥 Original Pasted Response</div>
                        <div class="section-content">
                            <details>
                                <summary style="cursor: pointer; color: #74b9ff;">Show original</summary>
                                <div style="margin-top: 0.5rem;">{_render_text_block(results["llm_response"])}</div>
                            </details>
                        </div>
                    </div>''')), unsafe_allow_html=True)
                else:
                    suffix = " (Verified Correct)" if response_category == "correct" else (" (Unverifiable)" if response_category == "unverifiable" else "")
                    st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
                        <div class="section-title">🤖 Pasted Response{suffix}</div>
                        <div class="section-content">{_render_text_block(results["llm_response"])}</div>
                    </div>''')), unsafe_allow_html=True)
        else:
            # For generated flows, just show the model's response (no verification line for clarity)
            st.markdown(_strip_leading_spaces(textwrap.dedent(f'''<div class="section-card">
                <div class="section-title">🤖 LLM Response{llm_time_text}</div>
                <div class="section-content">{_render_text_block(results["llm_response"])}</div>
            </div>''')), unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="margin-top: 3rem; padding: 1rem; text-align: center; color: #6c7293; font-size: 0.9rem;">
    <p>🛡️ NeuroShield - Securing AI interactions with enterprise-grade protection</p>
</div>
""", unsafe_allow_html=True)

