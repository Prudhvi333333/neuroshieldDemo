from __future__ import annotations
import json, math, re, time
from pathlib import Path
from typing import Any, Dict
from collections import defaultdict
import datetime
import threading
import subprocess
import sys

import streamlit as st

# Standard library & third-party
import os

# Import existing NeuroShield components
from langgraph_core.firewall_graph import build_firewall_graph, State
from api.client import NeuroShieldAPIClient

import logging
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Custom CSS for dark theme (same as app_updated.py)
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
    
    .api-status {
        color: #fdcb6e;
        font-weight: 600;
        text-shadow: 0 0 10px rgba(253, 203, 110, 0.4);
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

# Initialize API client
api_client = NeuroShieldAPIClient()

# Check API health status
api_health = api_client.health_check()
api_status = "🟢 Online" if api_health.get("status") == "healthy" else "🔴 Offline"

# Main header with API status
st.markdown(f"""
<div class="main-header">
    <h1 class="main-title">🛡️ NeuroShield GenAI Security Platform</h1>
    <p class="subtitle">Multi-tier security with real-time analysis of LLM traffic | API Status: <span class="api-status">{api_status}</span></p>
</div>
""", unsafe_allow_html=True)

# Create tabs for different modes
mode_tab, stats_tab = st.tabs(["🔒 Security Analysis", "📊 Statistics & Logs"])

with mode_tab:
    # Processing mode selection
    processing_mode = st.radio(
        "Select Processing Mode:",
        ["🚀 Direct Processing (Current)", "🌐 API Processing (New)"],
        help="Choose between direct LangGraph processing or FastAPI endpoint processing"
    )
    
    use_api = "API Processing" in processing_mode
    
    # Initialize session state for results
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = {}
    if "analysis_complete" not in st.session_state:
        st.session_state.analysis_complete = False

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

    # Button logic
    is_prompt_present = bool(prompt.strip())
    is_pasted_response_present = bool(pasted_llm_response.strip()) and paste_toggle
    analyze_button_disabled = not (is_prompt_present or is_pasted_response_present)

    # Analyze button with improved styling
    if st.button("🚀 Analyze Security", disabled=analyze_button_disabled, key="analyze_btn"):
        # Reset analysis state
        st.session_state.analysis_results = {}
        st.session_state.analysis_complete = False
        
        start_time = time.perf_counter()
        
        try:
            if use_api:
                # Use FastAPI endpoint
                with st.spinner("🌐 Analyzing via API..."):
                    api_result = api_client.analyze_prompt(
                        prompt=prompt,
                        llm_response=pasted_llm_response if paste_toggle else None
                    )
                
                if api_result.get("error"):
                    st.error(f"API Error: {api_result.get('reason', 'Unknown error')}")
                else:
                    st.session_state.analysis_results = {
                        "final_decision": api_result.get("classification", "Unknown"),
                        "risk_score": api_result.get("risk_score", 0.0),
                        "analysis_time": api_result.get("analysis_time", 0.0),
                        "attack_detection": api_result.get("attack_detection", {}),
                        "reason": api_result.get("reason", "No reason provided"),
                        "safe_prompt": api_result.get("final_prompt", ""),
                        "llm_response": api_result.get("llm_response", ""),
                        "verdict": api_result.get("verdict", ""),
                        "audit_id": api_result.get("audit_id", ""),
                        "processing_mode": "API"
                    }
                    st.session_state.analysis_complete = True
            else:
                # Use direct LangGraph processing (existing logic)
                graph = build_firewall_graph()
                initial_graph_state: State = {"user_prompt": prompt}
                if paste_toggle and pasted_llm_response:
                    initial_graph_state["llm_response"] = pasted_llm_response

                current_accumulated_state: State = initial_graph_state.copy()
                
                with st.spinner("🔍 Analyzing security..."):
                    for event in graph.stream(initial_graph_state):
                        if not isinstance(event, dict) or not event:
                            continue
                            
                        if "__node__" in event and len(event) == 1:
                            continue
                        else:
                            node_name = list(event.keys())[0]
                            payload = event[node_name]
                            if payload:
                                current_accumulated_state.update(payload)
                
                analysis_time = time.perf_counter() - start_time
                
                st.session_state.analysis_results = {
                    "final_decision": current_accumulated_state.get("classification", "Unknown"),
                    "risk_score": current_accumulated_state.get("risk_score", 0.0),
                    "analysis_time": analysis_time,
                    "attack_detection": current_accumulated_state.get("attack_detection", {}),
                    "reason": current_accumulated_state.get("reason", "No reason provided"),
                    "safe_prompt": current_accumulated_state.get("final_prompt", ""),
                    "llm_response": current_accumulated_state.get("llm_response", ""),
                    "verdict": current_accumulated_state.get("verdict", ""),
                    "processing_mode": "Direct"
                }
                st.session_state.analysis_complete = True
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Analysis failed: {e}")

    # Display results if analysis is complete
    if st.session_state.analysis_complete and st.session_state.analysis_results:
        results = st.session_state.analysis_results
        
        # Results container
        st.markdown('<div class="results-container">', unsafe_allow_html=True)
        
        # Analysis completed header with processing mode
        processing_mode_text = results.get("processing_mode", "Unknown")
        st.markdown(f'<div class="analysis-header">Analysis Completed ({processing_mode_text} Mode)</div>', unsafe_allow_html=True)
        
        # Top metrics
        st.markdown(f'''
        <div class="top-metrics">
            <div class="metric-card">
                <div class="metric-title">Final Decision</div>
                <div class="metric-value">{results["final_decision"]}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Risk Score</div>
                <div class="metric-value">{int(results["risk_score"] * 100)}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Analysis Time</div>
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
        
        # Reasoning section
        st.markdown(f'''
        <div class="section-card">
            <div class="section-title">🧠 Reasoning</div>
            <div class="section-content">{results["reason"]}</div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Verification verdict if available
        if results.get("verdict"):
            st.markdown(f'''
            <div class="section-card">
                <div class="section-title">✅ Verification Verdict</div>
                <div class="section-content">{results["verdict"]}</div>
            </div>
            ''', unsafe_allow_html=True)
        
        # Safe prompt section
        if results["safe_prompt"] and results["safe_prompt"] != prompt:
            st.markdown(f'''
            <div class="section-card">
                <div class="section-title">🔄 Alternate Safe Prompt</div>
                <div class="section-content">{results["safe_prompt"]}</div>
            </div>
            ''', unsafe_allow_html=True)
        
        # LLM Response section
        if results["llm_response"]:
            st.markdown(f'''
            <div class="section-card">
                <div class="section-title">🤖 LLM Response</div>
                <div class="section-content">{results["llm_response"]}</div>
            </div>
            ''', unsafe_allow_html=True)
        
        # API-specific information
        if results.get("audit_id"):
            st.markdown(f'''
            <div class="section-card">
                <div class="section-title">📋 Audit Information</div>
                <div class="section-content">Audit ID: {results["audit_id"]}</div>
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# Statistics and Logs tab
with stats_tab:
    if st.button("🔄 Refresh Statistics", key="refresh_stats"):
        st.rerun()
    
    # Get statistics from API
    stats = api_client.get_statistics()
    
    if not stats.get("error"):
        st.markdown("### 📊 Security Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Requests", stats["total_requests"])
        with col2:
            st.metric("Blocked", stats["blocked_requests"])
        with col3:
            st.metric("Risky", stats["risky_requests"])
        with col4:
            st.metric("Safe", stats["safe_requests"])
        
        st.metric("Average Risk Score", f"{stats['average_risk_score']:.3f}")
    else:
        st.error(f"Failed to load statistics: {stats.get('error')}")
    
    # Audit logs section
    st.markdown("### 📋 Recent Audit Logs")
    
    logs_data = api_client.get_audit_logs(limit=10)
    if not logs_data.get("error") and logs_data["logs"]:
        for i, log in enumerate(logs_data["logs"][:5]):  # Show last 5 logs
            with st.expander(f"Log {i+1}: {log.get('classification', 'Unknown')} - {log.get('timestamp', 'No timestamp')[:19]}"):
                st.json(log)
    else:
        st.info("No audit logs available or API error occurred")

# Document Scanner Integration (API-enabled)
st.markdown("---")
st.markdown("### 📄 Document Scanner")

uploaded_file = st.file_uploader("Upload document for scanning", type=["txt", "pdf", "docx"])

if uploaded_file is not None:
    if st.button("🔍 Scan Document", key="scan_doc"):
        with st.spinner("Scanning document..."):
            # Extract text content
            if uploaded_file.name.endswith('.txt'):
                content = uploaded_file.getvalue().decode('utf-8')
            else:
                # For PDF/DOCX, we'll use the API upload endpoint
                content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
            
            # Use API for document scanning
            scan_result = api_client.scan_document(uploaded_file.name, content)
            
            if not scan_result.get("error"):
                if scan_result["is_safe"]:
                    st.success(f"✅ Document '{uploaded_file.name}' is safe!")
                else:
                    st.warning(f"⚠️ Document '{uploaded_file.name}' contains sensitive information:")
                    for pattern, count in scan_result["sensitive_patterns"].items():
                        st.write(f"- {pattern}: {count} occurrences")
                
                st.info(f"Scan completed in {scan_result['scan_time']:.3f}s | Report ID: {scan_result['report_id']}")
            else:
                st.error("Document scan failed via API")

# Footer
st.markdown("""
<div style="margin-top: 3rem; padding: 1rem; text-align: center; color: #6c7293; font-size: 0.9rem;">
    <p>🛡️ NeuroShield - Securing AI interactions with enterprise-grade protection</p>
</div>
""", unsafe_allow_html=True)
