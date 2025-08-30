from __future__ import annotations
import time
from typing import Any, Dict
import datetime
import asyncio

import streamlit as st

# Assuming these imports are correctly set up and accessible
from orchestrator_enhanced import orchestrate_security_analysis

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
    
    # Start analysis with enhanced orchestration
    start_time = time.perf_counter()
    
    try:
        # Create progress bar for better UX
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔍 Initializing enhanced security analysis...")
        progress_bar.progress(10)
        
        # Use enhanced orchestration system
        context = {}
        if paste_toggle and pasted_llm_response:
            context["llm_response"] = pasted_llm_response
        
        with st.spinner("🔍 Analyzing security with enhanced agents..."):
            # Use enhanced orchestration with adaptive strategy
            orchestration_result = asyncio.run(orchestrate_security_analysis(
                prompt=prompt,
                context=context,
                strategy="adaptive"
            ))
            
            progress_bar.progress(90)
            status_text.text("🔍 Finalizing analysis...")
            
            # Convert orchestration result to expected format
            final_decision_obj = orchestration_result.get("final_decision", {})
            current_accumulated_state = {
                "classification": final_decision_obj.get("final_action", "unknown"),
                "risk_score": final_decision_obj.get("final_risk_score", 0.0),
                "attack_detection": orchestration_result.get("agent_results", {}).get("attack_detection", {}),
                "reason": f"Enhanced multi-agent analysis completed using {orchestration_result.get('strategy_used', 'adaptive')} strategy",
                "final_prompt": prompt,
                "llm_response": context.get("llm_response", "")
            }
        
        # Complete progress
        progress_bar.progress(100)
        status_text.text("✅ Enhanced analysis completed!")
        
        # Store results for display
        analysis_time = time.perf_counter() - start_time
        st.session_state.analysis_results = {
            "final_decision": current_accumulated_state.get("classification", "Unknown"),
            "risk_score": current_accumulated_state.get("risk_score", 0.0),
            "analysis_time": analysis_time,
            "attack_detection": current_accumulated_state.get("attack_detection", {}),
            "reason": current_accumulated_state.get("reason", "No reason provided"),
            "safe_prompt": current_accumulated_state.get("final_prompt", ""),
            "llm_response": current_accumulated_state.get("llm_response", "")
        }
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
    
    # Top 3 metrics side by side
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
        <div class="section-title">Reasoning</div>
        <div class="section-content">{results["reason"]}</div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Alternate safe prompt section
    if results["safe_prompt"] and results["safe_prompt"] != results.get("original_prompt", ""):
        st.markdown(f'''
        <div class="section-card">
            <div class="section-title">Alternate Safe Prompt</div>
            <div class="section-content">{results["safe_prompt"]}</div>
        </div>
        ''', unsafe_allow_html=True)
    
    # LLM Response section
    if results["llm_response"]:
        st.markdown(f'''
        <div class="section-card">
            <div class="section-title">LLM Response for Alternate Safe Prompt</div>
            <div class="section-content">{results["llm_response"]}</div>
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="margin-top: 3rem; padding: 1rem; text-align: center; color: #6c7293; font-size: 0.9rem;">
    <p>🛡️ NeuroShield - Securing AI interactions with enterprise-grade protection</p>
</div>
""", unsafe_allow_html=True)
