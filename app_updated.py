from __future__ import annotations
import json, math, re, time
from pathlib import Path
from typing import Any, Dict
from collections import defaultdict
import datetime
import time  # Ensure time is imported

import streamlit as st

# Standard library & third-party
import os

# Assuming these imports are correctly set up and accessible
from langgraph_core.firewall_graph import build_firewall_graph, State

import logging
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

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
        background: rgba(30, 30, 46, 0.9);
        padding: 2rem 1rem 1rem 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.5rem;
        text-shadow: 0 0 20px rgba(116, 185, 255, 0.3);
    }
    
    .subtitle {
        font-size: 1.1rem;
        color: #b4b4c8;
        margin-bottom: 0;
        font-weight: 400;
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
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 2rem !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
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
    
    .analysis-header {
        text-align: center;
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 2.5rem;
        padding: 1.5rem;
        background: linear-gradient(135deg, rgba(116, 185, 255, 0.2) 0%, rgba(9, 132, 227, 0.15) 100%);
        border-radius: 12px;
        border: 1px solid rgba(116, 185, 255, 0.3);
        text-shadow: 0 0 10px rgba(116, 185, 255, 0.5);
        position: relative;
        overflow: hidden;
    }
    
    .analysis-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
        animation: shimmer 2s infinite;
    }
    
    @keyframes shimmer {
        0% { left: -100%; }
        100% { left: 100%; }
    }
    
    .top-metrics {
        display: flex;
        gap: 1.5rem;
        margin-bottom: 2.5rem;
    }
    
    .metric-card {
        flex: 1;
        background: linear-gradient(135deg, rgba(45, 45, 68, 0.9) 0%, rgba(62, 62, 94, 0.8) 100%);
        padding: 2rem 1.5rem;
        border-radius: 14px;
        text-align: center;
        border: 1px solid rgba(116, 185, 255, 0.2);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
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
    
    .section-card {
        background: linear-gradient(135deg, rgba(45, 45, 68, 0.9) 0%, rgba(62, 62, 94, 0.8) 100%);
        padding: 2rem;
        border-radius: 14px;
        margin-bottom: 2rem;
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
        margin-bottom: 1.2rem;
        padding-bottom: 0.8rem;
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
        line-height: 1.7;
        font-size: 1.05rem;
        font-weight: 400;
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
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom loading animation */
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(116, 185, 255, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(116, 185, 255, 0); }
        100% { box-shadow: 0 0 0 0 rgba(116, 185, 255, 0); }
    }
    
    .pulse-animation {
        animation: pulse 2s infinite;
    }
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
st.markdown("""
<div class="main-header">
    <h1 class="main-title">🛡️ NeuroShield GenAI Security Platform</h1>
    <p class="subtitle">Multi-tier security with real-time analysis of LLM traffic</p>
</div>
""", unsafe_allow_html=True)

# Initialize session state for results
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = {}
if "analysis_complete" not in st.session_state:
    st.session_state.analysis_complete = False
if "current_step" not in st.session_state:
    st.session_state.current_step = 0

# Input section
st.markdown("""
<div class="input-section">
    <label class="input-label">Enter your prompt</label>
    <span class="input-description">Describe your request or question for the model...</span>
</div>
""", unsafe_allow_html=True)

prompt = st.text_area("Enter your prompt", height=120, key="prompt", placeholder="Type your prompt here...", label_visibility="collapsed")

# Paste LLM response toggle
paste_toggle = st.checkbox("🔄 Paste LLM response", key="paste_toggle_firewall", help="Enable this to paste an existing LLM response for verification")
pasted_llm_response = ""
if paste_toggle:
    pasted_llm_response = st.text_area("LLM Response", height=120, key="pasted_llm_response_area", placeholder="Paste the LLM response here...")

# Initialize placeholders for sequential sections
section_placeholders = {
    "metrics": st.empty(),
    "classification": st.empty(),
    "reasoning": st.empty(),
    "safe_prompt": st.empty(),
    "llm_response": st.empty()
}

# Button logic
is_prompt_present = bool(prompt.strip())
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
        "user_prompt": prompt,
        "classification": "",
        "risk_score": 0.0,
        "reason": "",
        "attack_detection": {},
        "final_prompt": "",
        "llm_response": ""
    }
    if paste_toggle and pasted_llm_response:
        initial_graph_state["llm_response"] = pasted_llm_response

    start_time = time.perf_counter()
    
    try:
        current_accumulated_state: State = initial_graph_state.copy()
        
        # Create progress bar for better UX
        progress_bar = st.progress(0)
        status_text = st.empty()
        
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
            "analysis_time": analysis_time,
            "attack_detection": current_accumulated_state.get("attack_detection", {}),
            "reason": current_accumulated_state.get("reason", "No reason provided"),
            "safe_prompt": current_accumulated_state.get("final_prompt", ""),
            "llm_response": current_accumulated_state.get("llm_response", ""),
            "bypass_used": current_accumulated_state.get("bypass_used", False),
            "rewrite_time": current_accumulated_state.get("rewrite_time", 0.0),
            "llm_time": current_accumulated_state.get("llm_time", 0.0),
            "verification_time": current_accumulated_state.get("verification_time", 0.0),
            "search_time": current_accumulated_state.get("search_time", 0.0),
            "response_verdict": current_accumulated_state.get("response_verdict", "Unknown")
        }
        
        # Debug: Print what we're storing in session state
        print(f"DEBUG Session State: {st.session_state.analysis_results}")
        st.session_state.analysis_complete = True
        
        # Clear progress indicators before rerun
        progress_bar.empty()
        status_text.empty()
        st.rerun()
        
    except Exception as e:
        st.error(f"Analysis failed: {e}")

# Display results if analysis is complete
if st.session_state.analysis_complete and st.session_state.analysis_results:
    results = st.session_state.analysis_results
    
    # Results container
    st.markdown('<div class="results-container">', unsafe_allow_html=True)
    
    # Analysis completed header
    st.markdown('<div class="analysis-header">Analysis Completed</div>', unsafe_allow_html=True)
    
    # Top 4 metrics side by side - with fallback handling
    classification = results.get("final_decision", "Unknown")
    risk_score = results.get("risk_score", 0.0)
    bypass_text = "⚡ Fast" if results.get("bypass_used") else "🧠 Deep"
    
    # Ensure risk_score is a number
    if not isinstance(risk_score, (int, float)):
        risk_score = 0.0
    
    st.markdown(f'''
    <div class="top-metrics">
        <div class="metric-card">
            <div class="metric-title">Classification</div>
            <div class="metric-value">{classification}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Risk Score</div>
            <div class="metric-value">{int(risk_score * 100)}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Analysis Type</div>
            <div class="metric-value">{bypass_text}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Total Time</div>
            <div class="metric-value">{results["analysis_time"]:.2f}s</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Classification section
    attack_types = []
    if results["attack_detection"]:
        for attack_type, details in results["attack_detection"].items():
            if isinstance(details, dict) and details.get("detected"):
                attack_types.append(attack_type.replace("_", " ").title())
    
    if attack_types:
        classification_text = f'<span class="threat-status">🚨 Threats Detected:</span> {", ".join(attack_types)}'
    else:
        classification_text = f'<span class="safe-status">✅ Security Analysis Complete:</span> Content passed all security checks successfully'
    
    st.markdown(f'''
    <div class="section-card">
        <div class="section-title">🔍 Security Classification</div>
        <div class="section-content">{classification_text}</div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Detailed Analysis section
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
    
    st.markdown(f'''
    <div class="section-card">
        <div class="section-title">🔍 Analysis Details</div>
        <div class="section-content">
            <strong>Reasoning:</strong> {results["reason"]}<br>
            <strong>Processing Breakdown:</strong> {timing_text}<br>
            <strong>Response Quality:</strong> {results.get("response_verdict", "Not verified")}
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Rewrite section (if applicable)
    if results["safe_prompt"] and results["safe_prompt"] != prompt:
        rewrite_time_text = f" (Generated in {results.get('rewrite_time', 0):.2f}s)" if results.get('rewrite_time', 0) > 0 else ""
        st.markdown(f'''
        <div class="section-card">
            <div class="section-title">🔄 Rewritten Safe Prompt{rewrite_time_text}</div>
            <div class="section-content">{results["safe_prompt"]}</div>
        </div>
        ''', unsafe_allow_html=True)
    
    # LLM Response section
    if results["llm_response"]:
        llm_time_text = f" (Generated in {results.get('llm_time', 0):.2f}s)" if results.get('llm_time', 0) > 0 else ""
        verify_time_text = f" (Verified in {results.get('verification_time', 0):.2f}s)" if results.get('verification_time', 0) > 0 else ""
        st.markdown(f'''
        <div class="section-card">
            <div class="section-title">🤖 LLM Response{llm_time_text}</div>
            <div class="section-content">{results["llm_response"]}</div>
            <div style="margin-top: 1rem; font-size: 0.9rem; color: #6c7293;">
                <strong>Verification:</strong> {results.get("response_verdict", "Not verified")}{verify_time_text}
            </div>
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="margin-top: 3rem; padding: 1rem; text-align: center; color: #6c7293; font-size: 0.9rem;">
    <p>🛡️ NeuroShield - Securing AI interactions with enterprise-grade protection</p>
</div>
""", unsafe_allow_html=True)
