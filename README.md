# NeuroShield Security Suite 🛡️
 
A comprehensive security solution for Large Language Models (LLMs) and sensitive document scanning, built with Streamlit, LangGraph, and Google Cloud Platform integrations. This suite addresses critical security and compliance concerns in enterprise AI deployments.
 
## 🌟 Overview
 
NeuroShield provides a multi-layered defense to analyze user prompts, verify LLM responses, and scan documents for confidential information, ensuring safer and more compliant AI interactions in enterprise environments.
 
## 🔒 Key Security Challenges Addressed
 
- Protection against complex prompt injections (including indirect ones)
- Consistent hallucination and harmful content detection
- Prevention of jailbreaking, model extraction, and scope violations
- Enhanced auditability, explainability, and zero-trust alignment
 
## ✨ Features
 
### 🔒 LLM Prompt Firewall
- **Multi-Stage Analysis**: LangGraph-orchestrated workflow for progressive prompt and response scrutiny
- **Risk Classification**: Categorizes prompts as "Safe," "Risky," or "Blocked"
- **Attack Detection**: Identifies prompt injection, jailbreaking attempts, PII leakage, and malicious code
- **Prompt Rewriting**: Converts "Risky" prompts to "Safe" versions
- **LLM Response Verification**: Validates factual accuracy and safety
- **Code Validation**: Analyzes code fragments for security vulnerabilities
- **Smart Processing**: Early blocking for high-risk prompts, fast-tracking for low-risk ones
- **Comprehensive Audit Logging**: All events logged to BigQuery
 
### 📄 Document Scanner
- **Sensitive Pattern Detection**: Scans documents for keywords, regex patterns, and high-entropy strings
- **GCP Integration**: Archives safe documents to Google Cloud Storage and logs reports to BigQuery
 
## 🚀 How It Works
 
### Prompt Firewall Workflow
1. **Initial Analysis**: Assesses user prompt for risk level and attack indicators
2. **Conditional Routing**: Directs to block, rewrite, or passthrough based on risk score
3. **LLM Interaction**: Processes the final prompt through the underlying LLM
4. **Response Verification**: Complete or streamlined verification based on risk level
5. **Audit Logging**: Records all interactions for compliance and analysis
 
### Document Scanner Workflow
1. **File Upload**: Accepts PDF, DOCX, or TXT files
2. **Text Extraction**: Extracts content from documents
3. **Pattern Analysis**: Scans for sensitive information patterns
4. **Action Routing**: Archives safe documents to GCS or logs warnings to BigQuery
 
## 🛠️ Installation & Setup
 
### Prerequisites
- Python 3.8+
- Google Cloud Platform account with enabled APIs:
  - Cloud Storage API
  - BigQuery API
 ### Steps
1. Clone the repository:
2. Create and activate a virtual environment:
3. Install dependencies:
4. Configure GCP authentication:
   - Create a service account with appropriate permissions
   - Download the key file
   - Set environment variable: `GOOGLE_APPLICATION_CREDENTIALS="path/to/keyfile.json"`
 
5. Update configuration in application files with your GCP project details
## ☁️ GCP Setup Requirements
 
1. **Storage Bucket**: For safe document archiving
2. **BigQuery Dataset**: With tables:
   - `events`: For prompt firewall audit logs
   - `scan_reports`: For document scanner warnings
 
## 🧪 Testing & Validation
 
- Unit tests for individual agents
- Integration tests for workflow validation
- Adversarial testing against known attack patterns
- End-to-end testing through the Streamlit UI
 
## 📚 Technology Stack
 
- **Frontend**: Streamlit
- **Orchestration**: LangGraph/LangChain
- **Document Processing**: PyMuPDF, python-docx
- **Cloud Services**: Google Cloud Storage, BigQuery
- **LLM Integration**: Configurable through `llm_utils.py`
 
## ⚠️ Limitations
 
- Pattern-based detection efficacy depends on pattern quality
- LLM fidelity impacts rewriting and verification quality
- Code validation provides initial defense but isn't exhaustive
- Streamlit may have scalability constraints for high-volume deployments
 
## 🤝 Contributing
 
Contributions welcome! Please fork the repository and submit pull requests.
 
6. Run the application: