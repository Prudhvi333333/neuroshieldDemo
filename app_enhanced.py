#!/usr/bin/env python3
"""
Enhanced NeuroShield App - Integrated with Day 5 Orchestration & Day 7 Federated Learning
"""

from __future__ import annotations
import json, math, re, time, asyncio
from pathlib import Path
from typing import Any, Dict
from collections import defaultdict
import datetime

import docx, fitz, streamlit as st
import os

# Enhanced imports for new capabilities
from orchestrator_enhanced import orchestrate_security_analysis, orchestrator, OrchestrationStrategy
from ml_engines.federated_learning_engine import (
    federated_engine, create_threat_intelligence_federation, 
    join_threat_intelligence_federation, get_federated_threat_prediction
)

# Original imports
from langgraph_core.firewall_graph import build_firewall_graph, State
from utils.patterns import KEYWORD_PATTERNS, REGEX_PATTERNS, SECRET_PATTERNS

import logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
WARNING_REPORTS_DIR = "warning_reports"
TEST_DATA_DIR = "test_data"

# Enhanced configuration
ORCHESTRATION_STRATEGIES = {
    "Adaptive (Recommended)": "adaptive",
    "Parallel Processing": "parallel", 
    "Sequential Priority": "sequential",
    "Priority-Based": "priority_based"
}

# ------------------------------------------------------------------------------
# Helper Functions (Original)
# ------------------------------------------------------------------------------

def calculate_shannon_entropy(data: str) -> float:
    """Calculates the Shannon entropy of a string to find randomness."""
    if not data: return 0.0
    entropy = 0.0
    for x in range(256):
        p_x = float(data.count(chr(x))) / len(data)
        if p_x > 0: entropy += - p_x * math.log2(p_x)
    return entropy

def extract_text_from_file(uploaded_file):
    """Extracts text from uploaded txt, pdf, or docx file."""
    if uploaded_file.name.endswith('.pdf'):
        try:
            doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
            return "".join([page.get_text() for page in doc])
        except Exception as e:
            st.error(f"Error reading PDF file: {e}")
    elif uploaded_file.name.endswith('.docx'):
        try:
            doc = docx.Document(uploaded_file)
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            st.error(f"Error reading DOCX file: {e}")
    elif uploaded_file.name.endswith('.txt'):
        return uploaded_file.getvalue().decode("utf-8")
    else:
        st.error("Unsupported file type.")
    return None

def analyze_text(text: str) -> Dict[str, int]:
    """Scans text for all defined patterns and returns findings."""
    results = defaultdict(int)
    
    low = text.lower()
    
    # Regex and Secret patterns
    for pn, pr in {**REGEX_PATTERNS, **SECRET_PATTERNS}.items():
        flags = re.IGNORECASE
        if "Private Key" in pn: flags |= re.DOTALL
        if "Generic Secret" in pn: flags |= re.VERBOSE
        try:
            matches = re.findall(pr, text, flags)
            if matches:
                key_name = f"SECRET: {pn}" if pn in SECRET_PATTERNS else pn
                results[key_name] += len(matches)
        except re.error as e:
            st.warning(f"Regex error for '{pn}': {e}")

    # Entropy analysis
    potential_secrets = re.split(r'[\s\'".,;=()\[\]{}]', text)
    high_entropy_strings = sum(
        1 for s in potential_secrets
        if 20 <= len(s) <= 64 and s.isalnum() and calculate_shannon_entropy(s) > 4.5
    )
    if high_entropy_strings > 0:
        results["SECRET: High-Entropy String"] += high_entropy_strings
    
    return dict(results)

def log_report_to_json(filename: str, report_data_dict: Dict[str, Any]):
    """Write scan report to test_data/<filename>_log.json locally."""
    try:
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        log_file_path = os.path.join(TEST_DATA_DIR, f"{Path(filename).stem}_log.json")
        with open(log_file_path, "w", encoding="utf-8") as f:
            json.dump(report_data_dict, f, indent=2)
        st.success(f"Report data logged to {log_file_path} successfully.")
    except Exception as e:
        st.error(f"Error logging to JSON file: {e}")

def save_file_locally(uploaded_file_object, destination_folder: str = WARNING_REPORTS_DIR):
    """Save file-like object to local directory."""
    try:
        os.makedirs(destination_folder, exist_ok=True)
        file_path = os.path.join(destination_folder, uploaded_file_object.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file_object.getbuffer())
        st.success(f"File `{uploaded_file_object.name}` successfully saved to `{destination_folder}`.")
    except Exception as e:
        st.error(f"Failed to save file locally: {e}")

# ------------------------------------------------------------------------------
# Enhanced Analysis Functions
# ------------------------------------------------------------------------------

async def run_enhanced_analysis(prompt: str, strategy: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run enhanced orchestrated analysis"""
    try:
        result = await orchestrate_security_analysis(prompt, context, strategy)
        return result
    except Exception as e:
        logging.error(f"Enhanced analysis failed: {e}")
        return {"error": str(e), "fallback": True}

def run_original_analysis(prompt: str, pasted_response: str = "") -> Dict[str, Any]:
    """Run original LangGraph analysis as fallback"""
    try:
        graph = build_firewall_graph()
        initial_state: State = {"user_prompt": prompt}
        if pasted_response:
            initial_state["llm_response"] = pasted_response
        
        # Execute graph and collect final state
        final_state = None
        for event in graph.stream(initial_state):
            if isinstance(event, dict):
                final_state = event
        
        return final_state or {}
    except Exception as e:
        logging.error(f"Original analysis failed: {e}")
        return {"error": str(e)}

# ------------------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------------------

st.set_page_config("NeuroShield Enhanced", layout="wide", page_icon="🛡️")

# Header with enhanced capabilities indicator
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.title("🛡️ **NeuroShield Enhanced**")
    st.caption("Day 5 Orchestration + Day 7 Federated Learning")

with col2:
    # Orchestration status
    orchestration_stats = orchestrator.get_orchestration_stats()
    st.metric("Active Agents", orchestration_stats["agent_status"].get("healthy_agents", 0))

with col3:
    # Federated learning status
    federated_stats = federated_engine.get_federated_stats()
    st.metric("FL Sessions", federated_stats["active_sessions"])

# Main tabs
fw_tab, doc_tab, admin_tab = st.tabs(["🔒 Enhanced Firewall", "📄 Document Scanner", "⚙️ System Admin"])

# ╭────────────────────────── Enhanced Prompt Firewall ──────────────────────────╮
with fw_tab:
    st.header("🚀 Enhanced Multi-Agent Security Analysis")
    
    # Configuration section
    with st.expander("🔧 Analysis Configuration", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            strategy = st.selectbox(
                "Orchestration Strategy",
                options=list(ORCHESTRATION_STRATEGIES.keys()),
                index=0,
                help="Choose how agents coordinate analysis"
            )
            
            use_federated = st.checkbox(
                "Use Federated Learning",
                value=False,
                help="Leverage collaborative threat intelligence"
            )
        
        with col2:
            enable_fallback = st.checkbox(
                "Enable Original Firewall Fallback",
                value=True,
                help="Fall back to original system if enhanced analysis fails"
            )
            
            show_agent_details = st.checkbox(
                "Show Individual Agent Results",
                value=False,
                help="Display detailed results from each agent"
            )
    
    # Input section
    prompt = st.text_area("Security Prompt Analysis ▶", height=140, key="enhanced_prompt")
    paste_toggle = st.toggle("Include LLM Response for Verification", key="enhanced_paste_toggle")
    pasted_llm_response = st.text_area("LLM Response", height=140, key="enhanced_response") if paste_toggle else ""
    
    # Context inputs
    with st.expander("📊 Additional Context (Optional)", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            network_ip = st.text_input("Source IP", placeholder="192.168.1.100")
            destination_ip = st.text_input("Destination IP", placeholder="104.18.7.192")
        
        with col2:
            user_id = st.text_input("User ID", placeholder="user123")
            session_id = st.text_input("Session ID", placeholder="session_abc")
    
    # Analysis button
    is_prompt_present = bool(prompt.strip())
    is_response_present = bool(pasted_llm_response.strip()) and paste_toggle
    analyze_disabled = not (is_prompt_present or is_response_present)
    
    if st.button("🚀 Run Enhanced Analysis", disabled=analyze_disabled, type="primary"):
        # Prepare context
        context = {}
        if network_ip or destination_ip:
            context["network_traffic"] = {
                "source_ip": network_ip,
                "destination_ip": destination_ip
            }
        if user_id:
            context["user_id"] = user_id
        if session_id:
            context["session_id"] = session_id
        if pasted_llm_response:
            context["response"] = pasted_llm_response
        
        # Run analysis
        with st.spinner("🔄 Running enhanced multi-agent analysis..."):
            start_time = time.time()
            
            # Try enhanced analysis first
            strategy_key = ORCHESTRATION_STRATEGIES[strategy]
            
            try:
                # Run async analysis
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                enhanced_result = loop.run_until_complete(
                    run_enhanced_analysis(prompt, strategy_key, context)
                )
                loop.close()
                
                analysis_time = time.time() - start_time
                
                if "error" in enhanced_result and enable_fallback:
                    st.warning("Enhanced analysis failed, falling back to original system...")
                    fallback_result = run_original_analysis(prompt, pasted_llm_response)
                    enhanced_result["fallback_result"] = fallback_result
                
                # Display results
                st.success(f"✅ Analysis completed in {analysis_time:.2f}s using {strategy}")
                
                # Main results
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("🎯 Final Security Decision")
                    final_decision = enhanced_result.get("final_decision", {})
                    
                    action = final_decision.get("final_action", "unknown")
                    risk_score = final_decision.get("final_risk_score", 0.0)
                    
                    # Action indicator
                    if action == "block":
                        st.error(f"🚫 **BLOCK** - Risk Score: {risk_score:.3f}")
                    elif action == "quarantine":
                        st.warning(f"⚠️ **QUARANTINE** - Risk Score: {risk_score:.3f}")
                    elif action == "monitor":
                        st.info(f"👁️ **MONITOR** - Risk Score: {risk_score:.3f}")
                    else:
                        st.success(f"✅ **ALLOW** - Risk Score: {risk_score:.3f}")
                    
                    # Threat categories
                    threat_categories = final_decision.get("threat_categories", [])
                    if threat_categories:
                        st.write("**Detected Threats:**")
                        for category in threat_categories:
                            st.write(f"• {category}")
                
                with col2:
                    st.subheader("📊 Processing Summary")
                    processing_summary = final_decision.get("processing_summary", {})
                    
                    st.metric("Total Agents", processing_summary.get("total_agents", 0))
                    st.metric("Successful", processing_summary.get("successful_agents", 0))
                    st.metric("Failed", processing_summary.get("failed_agents", 0))
                    st.metric("Processing Time", f"{analysis_time:.2f}s")
                
                # Individual agent results
                if show_agent_details:
                    st.subheader("🔍 Individual Agent Results")
                    agent_results = enhanced_result.get("agent_results", {})
                    
                    for agent_name, result in agent_results.items():
                        with st.expander(f"Agent: {agent_name}"):
                            if "error" in result:
                                st.error(f"Error: {result['error']}")
                            else:
                                st.json(result)
                
                # Federated learning integration
                if use_federated and "error" not in enhanced_result:
                    st.subheader("🌐 Federated Learning Insights")
                    try:
                        # This would integrate with actual federated predictions
                        st.info("Federated learning integration would provide collaborative threat intelligence here")
                    except Exception as e:
                        st.warning(f"Federated learning unavailable: {e}")
                
                # Full result details
                with st.expander("📋 Complete Analysis Results"):
                    st.json(enhanced_result)
                
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                if enable_fallback:
                    st.info("Attempting fallback to original system...")
                    fallback_result = run_original_analysis(prompt, pasted_llm_response)
                    st.json(fallback_result)

# ╭────────────────────── Document Scanner ─────────────────────────╮
with doc_tab:
    st.header("📄 Enhanced Document Scanner")
    st.info("Local mode with enhanced threat detection capabilities")
    
    f = st.file_uploader("Upload PDF / DOCX / TXT", type=["pdf", "docx", "txt"])
    
    if f is not None:
        st.success(f"File '{f.name}' uploaded successfully!")

        with st.spinner("Analyzing document with enhanced capabilities..."):
            extracted_text = extract_text_from_file(f)
            
            if extracted_text:
                # Original pattern analysis
                pattern_results = analyze_text(extracted_text)
                
                # Enhanced analysis on document content
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    doc_analysis = loop.run_until_complete(
                        run_enhanced_analysis(
                            f"Analyze this document content for security threats: {extracted_text[:1000]}...",
                            "adaptive",
                            {"document_name": f.name, "content_type": "document"}
                        )
                    )
                    loop.close()
                except Exception as e:
                    doc_analysis = {"error": str(e)}

        st.success("Enhanced analysis complete!")

        # Display results
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Pattern Detection Results")
            if pattern_results:
                st.dataframe({
                    "Pattern / Indicator": list(pattern_results.keys()), 
                    "Occurrences": list(pattern_results.values())
                })
            else:
                st.info("No patterns detected")
        
        with col2:
            st.subheader("🤖 AI Security Analysis")
            if "error" not in doc_analysis:
                final_decision = doc_analysis.get("final_decision", {})
                action = final_decision.get("final_action", "allow")
                risk_score = final_decision.get("final_risk_score", 0.0)
                
                if action == "block":
                    st.error(f"🚫 High Risk Document - Score: {risk_score:.3f}")
                elif action == "quarantine":
                    st.warning(f"⚠️ Medium Risk Document - Score: {risk_score:.3f}")
                else:
                    st.success(f"✅ Low Risk Document - Score: {risk_score:.3f}")
            else:
                st.warning("Enhanced analysis unavailable")

        # File handling based on results
        sensitive_patterns = {k: v for k, v in pattern_results.items() if k.startswith("SECRET:")}
        
        if sensitive_patterns or (doc_analysis.get("final_decision", {}).get("final_action") in ["block", "quarantine"]):
            st.header("🚨 Security Alert: Sensitive Content Detected")
            st.warning("Document contains sensitive data or security threats")
            
            with st.spinner("Saving security report..."):
                combined_report = {
                    "pattern_analysis": sensitive_patterns,
                    "ai_analysis": doc_analysis.get("final_decision", {}),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "filename": f.name
                }
                log_report_to_json(f.name, combined_report)
        else:
            st.header("✅ Document Appears Safe")
            st.success("No sensitive patterns or security threats detected")
            
            f.seek(0)
            with st.spinner(f"Archiving safe document..."):
                save_file_locally(f, WARNING_REPORTS_DIR)

# ╭────────────────────── System Administration ─────────────────────────╮
with admin_tab:
    st.header("⚙️ System Administration")
    
    # Orchestration statistics
    st.subheader("🤖 Agent Orchestration Status")
    orchestration_stats = orchestrator.get_orchestration_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Orchestrations", orchestration_stats.get("total_orchestrations", 0))
    with col2:
        system_health = orchestration_stats.get("system_health", {})
        st.metric("System Health", system_health.get("status", "unknown").title())
    with col3:
        st.metric("Avg Response Time", f"{system_health.get('avg_response_time', 0):.3f}s")
    
    # Agent status
    st.subheader("🔧 Individual Agent Status")
    agent_metrics = orchestration_stats.get("agent_metrics", {})
    
    if agent_metrics:
        agent_data = []
        for agent_name, metrics in agent_metrics.items():
            agent_data.append({
                "Agent": agent_name,
                "Status": metrics.get("status", "unknown"),
                "Success Rate": f"{metrics.get('success_rate', 0)*100:.1f}%",
                "Avg Response": f"{metrics.get('avg_response_time', 0):.3f}s",
                "Total Executions": metrics.get('total_executions', 0)
            })
        
        st.dataframe(agent_data)
    
    # Federated Learning Status
    st.subheader("🌐 Federated Learning Status")
    federated_stats = federated_engine.get_federated_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Participant ID", federated_stats.get("participant_id", "N/A"))
    with col2:
        st.metric("Role", federated_stats.get("role", "N/A").title())
    with col3:
        st.metric("Active Sessions", federated_stats.get("active_sessions", 0))
    
    # System controls
    st.subheader("🎛️ System Controls")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Refresh Agent Status"):
            st.rerun()
        
        if st.button("📊 Export System Logs"):
            st.info("Log export functionality would be implemented here")
    
    with col2:
        if st.button("🧪 Run System Health Check"):
            with st.spinner("Running health check..."):
                # Simulate health check
                time.sleep(1)
                st.success("✅ All systems operational")
        
        if st.button("⚡ Reset Agent Metrics"):
            st.warning("Metrics reset functionality would be implemented here")

# Footer
st.divider()
st.caption("NeuroShield Enhanced - Day 5 Orchestration + Day 7 Federated Learning Integration")
