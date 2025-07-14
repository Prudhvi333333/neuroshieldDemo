from __future__ import annotations
import json, math, re, time
from pathlib import Path
from typing import Any, Dict
from collections import defaultdict
import datetime # Import for BigQuery timestamp

import docx, fitz, streamlit as st

# Required for Google Cloud integrations
from google.cloud import storage
from google.cloud import bigquery

# Assuming these imports are correctly set up and accessible
from langgraph_core.firewall_graph import build_firewall_graph, State
from utils.patterns import KEYWORD_PATTERNS, REGEX_PATTERNS, SECRET_PATTERNS

# ==============================================================================
# --- GCP CONFIGURATION - REPLACE WITH YOUR GCP DETAILS ---
# ==============================================================================
# GCS Bucket for storing original files deemed safe
GCS_BUCKET_NAME = "neuroshield_safe_docs"

# BigQuery details for logging unsafe document reports
# IMPORTANT: Replace "YOUR_GCP_PROJECT_ID" with your actual Google Cloud Project ID
BQ_PROJECT_ID = "" # <-- Update this with your project ID
BQ_DATASET_ID = "neuroshield_logs"
BQ_TABLE_ID = "scan_reports"
# ==============================================================================


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

def log_report_to_bigquery(project_id: str, dataset_id: str, table_id: str, filename: str, report_data_dict: Dict[str, Any]):
    """Inserts a scan report into a BigQuery table."""
    try:
        client = bigquery.Client(project=project_id)
        table_full_id = f"{project_id}.{dataset_id}.{table_id}"
        
        # BigQuery expects a list of dictionaries for rows.
        # Ensure report_data_dict is JSON stringified before inserting.
        rows_to_insert = [{
            "filename": filename,
            "upload_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scan_result": "unsafe",
            "report_data": json.dumps(report_data_dict)
        }]
        
        errors = client.insert_rows_json(table_full_id, rows_to_insert)
        if not errors:
            st.success(f"BigQuery: Warning report for `{filename}` successfully logged.")
        else:
            st.error(f"BigQuery: Errors occurred while inserting rows: {errors}")
    except Exception as e:
        st.error(f"BigQuery: Failed to log report: {e}")

def upload_to_gcs(bucket_name: str, uploaded_file_object, destination_blob_name: str):
    """Uploads a file to the specified GCS bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        
        # Upload using the file-like object directly
        blob.upload_from_file(uploaded_file_object, rewind=True) 
        
        st.success(f"GCS: File `{destination_blob_name}` successfully uploaded to bucket `{bucket_name}`.")
    except Exception as e:
        st.error(f"GCS: Failed to upload file: {e}")
# ╰───────────────────────────────────────────────────────────────────╯


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
            "fast": "ResponseVerifierAgent", # 'fast' is a node in the graph, maps to ResponseVerifierAgent tab
            "block": "Final Results",
            "audit": "Final Results",
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

                        current_accumulated_state.update(payload_from_node)
                        payload_for_display = payload_from_node
                    
                    if node_name_from_event:
                        label = label_map.get(node_name_from_event)

                        if label:
                            placeholders[label].json(payload_for_display, expanded=True) # JSON expanded
                            st.session_state.firewall_results[label] = payload_for_display

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
        **GCP Integration Note:** This document scanner attempts to log sensitive findings to Google BigQuery
        and store safe documents in Google Cloud Storage. Ensure your environment has the `GOOGLE_APPLICATION_CREDENTIALS`
        environment variable set and that your service account has the necessary IAM permissions for BigQuery
        (`BigQuery Data Editor`) and Cloud Storage (`Storage Object Creator`).
        Also, ensure the BigQuery table `neuroshield_logs.scan_reports` exists with the correct schema.
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
            st.warning("The following types of potentially sensitive data were identified. This report will be logged to BigQuery.")
            for pattern_name in sensitive_patterns_found.keys():
                st.markdown(f"- **{pattern_name}**")

            # Log the detailed report to BigQuery
            with st.spinner("Logging warning report to BigQuery..."):
                log_report_to_bigquery(
                    project_id=BQ_PROJECT_ID,
                    dataset_id=BQ_DATASET_ID,
                    table_id=BQ_TABLE_ID,
                    filename=f.name,
                    report_data_dict=sensitive_patterns_found
                )
        else:
            # === Safe Document Workflow ===
            st.header("✅ Document Appears Safe")
            st.success("No sensitive data patterns were detected. This document will be archived to Google Cloud Storage.")

            # To upload, we need to rewind the uploaded file object
            # The `upload_from_file` method expects a file-like object and will read from its current position.
            # `f.seek(0)` ensures we read from the beginning.
            f.seek(0) 

            # Upload the file to GCS
            with st.spinner(f"Archiving `{f.name}` to Google Cloud Storage..."):
                upload_to_gcs(
                    bucket_name=GCS_BUCKET_NAME,
                    uploaded_file_object=f, # Pass the file-like object directly
                    destination_blob_name=f.name
                )

