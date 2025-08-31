from __future__ import annotations
import json, math, re, time
from pathlib import Path
from typing import Any, Dict
from collections import defaultdict
import datetime # Import for BigQuery timestamp

import docx, fitz, streamlit as st

# Standard library & third-party
import os

# Assuming these imports are correctly set up and accessible
from langgraph_core.firewall_graph import build_firewall_graph, State
from utils.patterns import KEYWORD_PATTERNS, REGEX_PATTERNS, SECRET_PATTERNS

import logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# ------------------------------------------------------------------------------
# Local storage configuration – fully offline
# ------------------------------------------------------------------------------
WARNING_REPORTS_DIR = "warning_reports"  # where safe documents are archived
TEST_DATA_DIR = "test_data"              # where JSON scan reports are saved


# ╭───────────── Document-scanner helpers (Integrated with GCP) ─────────────╮

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
    """Scans text for all defined patterns (regex, secrets, high-entropy) and returns a dictionary of findings."""
    results = defaultdict(int)
    
    # Keyword analysis (kept from original streamlit_app.py but modified to group by category if needed)
    # The provided app.py had this commented out. If you *only* want secrets to BQ, you can remove this.
    # For now, keeping it as it was in your original UI code, but ensuring 'SECRET:' prefix for secrets.
    low = text.lower()
    # for cat, keys in KEYWORD_PATTERNS.items():
    # for k in keys:
        # c = low.count(k.lower())
        #     if c:
        #         results[f"Keyword: {cat} - {k}"] += c # More specific labeling

    # Regex and Secret patterns
    for pn, pr in {**REGEX_PATTERNS, **SECRET_PATTERNS}.items():
        flags = re.IGNORECASE
        if "Private Key" in pn: flags |= re.DOTALL
        if "Generic Secret" in pn: flags |= re.VERBOSE
        try:
            matches = re.findall(pr, text, flags)
            if matches:
                 # Add 'SECRET:' prefix only for patterns explicitly in SECRET_PATTERNS
                key_name = f"SECRET: {pn}" if pn in SECRET_PATTERNS else pn
                results[key_name] += len(matches)
        except re.error as e:
            st.warning(f"Regex error for '{pn}': {e}") # Use st.warning instead of st.error for regex issues, so it doesn't stop execution

    # Entropy analysis
    potential_secrets = re.split(r'[\s\'".,;=()\[\]{}]', text)
    # Filter for longer alphanumeric strings for entropy
    high_entropy_strings = sum(
        1 for s in potential_secrets
        if 20 <= len(s) <= 64 and s.isalnum() and calculate_shannon_entropy(s) > 4.5
    )
    if high_entropy_strings > 0:
        results["SECRET: High-Entropy String"] += high_entropy_strings
    
    return dict(results) # Convert back to dict for cleaner display/storage

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

# ----------------- END LOCAL HELPERS -----------------

st.set_page_config("NeuroShield", layout="wide", page_icon="🛡️")
st.title("🛡️ **NeuroShield**")

fw_tab, doc_tab = st.tabs(["🔒 Prompt Firewall", "📄 Document Scanner"])

# ╭────────────────────────── Prompt Firewall ──────────────────────────╮
with fw_tab:
    # Initialize session state for firewall results if not already present
    if "firewall_results" not in st.session_state:
        st.session_state.firewall_results = {}

    prompt = st.text_area("Prompt ▶", height=140, key="prompt")
    paste_toggle = st.toggle("Paste existing LLM response for verification", key="paste_toggle_firewall")
    pasted_llm_response = st.text_area("LLM Response", height=140, key="pasted_llm_response_area") if paste_toggle else ""

    # Define the order of agents/tabs (these are UI tab names)
    agent_order = [
        "PromptScanAgent", "AttackDetection", "SafePromptAgent",
        "LLM Response", "ResponseVerifierAgent", "CodeValidationAgent", "Final Results"
    ]

    # Create tab objects and placeholders on every rerun.
    tab_objs = st.tabs(agent_order)
    placeholders = {n: t.empty() for n, t in zip(agent_order, tab_objs)}

    # Corrected disabled logic for the button: enabled if either prompt or pasted response has content (if toggle is on)
    is_prompt_present = bool(prompt.strip())
    is_pasted_response_present = bool(pasted_llm_response.strip()) and paste_toggle
    
    # The button should be disabled ONLY if both are absent or toggle is off and prompt is absent
    analyze_button_disabled = not (is_prompt_present or is_pasted_response_present)

    if st.button("Analyze Security 🚀", disabled=analyze_button_disabled):
        # ... rest of your analysis logic ...
        # Clear previous results visually and in session state at the very beginning of a new analysis
        st.session_state.firewall_results = {}
        for agent_name in agent_order:
            placeholders[agent_name].empty() # Clear out old content in the UI

        graph = build_firewall_graph()
        
        # Initial state for the graph. Populate llm_response here if pasting.
        initial_graph_state: State = {"user_prompt": prompt}
        if paste_toggle and pasted_llm_response:
            initial_graph_state["llm_response"] = pasted_llm_response

        start = time.perf_counter()

        # Mapping of LangGraph node names to UI tab labels
        label_map = {
            "analysis": "PromptScanAgent",
            "rewrite": "SafePromptAgent",
            "llm": "LLM Response",
            "verify": "ResponseVerifierAgent",
            "verify_final": "ResponseVerifierAgent",  # final verifier state with reason/verdict
            "fast": "ResponseVerifierAgent", # 'fast' is a node in the graph, maps to ResponseVerifierAgent tab
            "block": "Final Results",
            "audit": "Final Results",
            "search": "ResponseVerifierAgent",  # ensure second-pass verifier results appear
        }

        # Nodes that run but do not require a dedicated display tab (and shouldn't trigger warnings)
        NODES_TO_SKIP_DISPLAY = ["passthrough"]

        try:
            current_accumulated_state: State = initial_graph_state.copy()

            with st.spinner("Analyzing security..."): # Spinner for the entire graph execution
                for event in graph.stream(initial_graph_state):
                    node_name_from_event = None
                    payload_for_display = None

                    if not isinstance(event, dict) or not event:
                        st.warning(f"Unexpected event type from graph.stream: {type(event)}, value: {event}")
                        continue

                    # Determine the node name and the state update/full state from the event
                    if "__node__" in event and len(event) == 1:
                        node_name_from_event = event["__node__"]
                        payload_for_display = current_accumulated_state
                    else:
                        node_name_from_event = list(event.keys())[0]
                        payload_from_node = event[node_name_from_event]

                        # Guard: some nodes may emit None; convert to empty dict
                        if payload_from_node is None:
                            payload_from_node = {}

                        current_accumulated_state.update(payload_from_node)
                        payload_for_display = payload_from_node
                        print(f"DEBUG: Updated state with {node_name_from_event}: {list(payload_from_node.keys())}")
                        if node_name_from_event in ['verify', 'verify_final', 'search'] and any(k in payload_from_node for k in ['reason', 'verdict', 'confidence']):
                            print(f"DEBUG: VERIFIER EVENT {node_name_from_event} - payload: {payload_from_node}")
                    
                    if node_name_from_event:
                        label = label_map.get(node_name_from_event)

                        if label:
                            # For verifier tab, show the **full** accumulated state so second-pass
                            # fields (reason, confidence) appear even if this event payload came
                            # from the 'search' node or an earlier verifier run.
                            if label == "ResponseVerifierAgent":
                                display_data = current_accumulated_state
                            else:
                                display_data = payload_for_display

                            placeholders[label].json(display_data, expanded=True)
                            st.session_state.firewall_results[label] = display_data

                            # Special handling for "AttackDetection" tab:
                            if label == "PromptScanAgent" and "attack_detection" in payload_for_display:
                                placeholders["AttackDetection"].json(payload_for_display["attack_detection"], expanded=True) # JSON expanded
                                st.session_state.firewall_results["AttackDetection"] = payload_for_display["attack_detection"]

                            # Special handling for "CodeValidationAgent" tab:
                            if label == "ResponseVerifierAgent" and "code_verdict" in current_accumulated_state:
                                code_validation_data = {
                                    "code_verdict": current_accumulated_state.get("code_verdict"),
                                    "code_fragment": current_accumulated_state.get("code_fragment")
                                }
                                placeholders["CodeValidationAgent"].json(code_validation_data, expanded=True) # JSON expanded
                                st.session_state.firewall_results["CodeValidationAgent"] = code_validation_data

                        elif node_name_from_event in NODES_TO_SKIP_DISPLAY:
                            pass
                        else:
                            st.warning(f"Node '{node_name_from_event}' completed but has no mapped UI tab or explicit skip. Event: {event}")

            print("DEBUG final state keys:", list(current_accumulated_state.keys()))
            print("DEBUG final accumulated state verifier fields:", {k: v for k, v in current_accumulated_state.items() if k in ['reason', 'verdict', 'confidence']})
            
            # EMERGENCY FIX: Force verifier fields into session state if missing from accumulated state
            if 'reason' not in current_accumulated_state and 'ResponseVerifierAgent' in st.session_state.firewall_results:
                verifier_data = st.session_state.firewall_results['ResponseVerifierAgent']
                if isinstance(verifier_data, dict) and 'reason' in verifier_data:
                    print("DEBUG: Forcing verifier data from session state")
                    placeholders['ResponseVerifierAgent'].json(verifier_data, expanded=True)
            
            st.success(f"✅ Completed in {time.perf_counter()-start:.2f} s")

        except Exception as e:
            st.error(f"An error occurred during analysis: {e}")
            import traceback
            st.code(traceback.format_exc())

    for agent_name in agent_order:
        if agent_name in st.session_state.firewall_results:
            placeholders[agent_name].json(st.session_state.firewall_results[agent_name], expanded=True) # JSON expanded

# ╭────────────────────── Document Scanner (Integrated with GCP) ─────────────────────────╮
with doc_tab:
    st.info("""
        **Local Mode:** This document scanner logs sensitive findings to JSON files in `test_data/` and archives safe documents into the `warning_reports/` folder. No internet or cloud services are required.
        """)
    
    f = st.file_uploader("Upload PDF / DOCX / TXT", type=["pdf", "docx", "txt"])
    
    if f is not None:
        st.success(f"File '{f.name}' uploaded successfully!")

        with st.spinner("Analyzing document..."):
            extracted_text = extract_text_from_file(f)
            pattern_results = analyze_text(extracted_text) if extracted_text else {}

        st.success("Analysis complete!")

        # Filter for sensitive patterns (those prefixed with "SECRET:")
        sensitive_patterns_found = {k: v for k, v in pattern_results.items() if k.startswith("SECRET:")}

        # Display full scan results in a table
        if pattern_results:
            st.header("📊 Full Scan Results")
            st.dataframe({ "Pattern / Indicator": list(pattern_results.keys()), "Occurrences": list(pattern_results.values()) })
        else:
            st.info("No patterns of any kind were detected in the document.")

        st.divider()

        # --- Main Workflow: Route document based on scan results ---
        if sensitive_patterns_found:
            # === Unsafe Document Workflow ===
            st.header("🚨 Warning: Unsafe Document Detected")
            st.warning("The following sensitive data types were identified. A JSON report will be saved locally.")
            for pattern_name in sensitive_patterns_found.keys():
                st.markdown(f"- **{pattern_name}**")

            # Log the detailed report to local JSON
            with st.spinner("Saving warning report locally..."):
                log_report_to_json(
                    filename=f.name,
                    report_data_dict=sensitive_patterns_found
                )
        else:
            # === Safe Document Workflow ===
            st.header("✅ Document Appears Safe")
            st.success("No sensitive data patterns were detected. This document will be archived locally.")

            # To upload, we need to rewind the uploaded file object
            # The `upload_from_file` method expects a file-like object and will read from its current position.
            # `f.seek(0)` ensures we read from the beginning.
            f.seek(0) 

            # Upload the file to local archive
            with st.spinner(f"Archiving `{f.name}` locally to `{WARNING_REPORTS_DIR}`..."):
                save_file_locally(
                    uploaded_file_object=f, # Pass the file-like object directly
                    destination_folder=WARNING_REPORTS_DIR
                )
