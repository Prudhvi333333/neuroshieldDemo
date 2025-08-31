from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from api.client import NeuroShieldAPIClient
from api.async_endpoints import router as async_router
from typing import Optional, Dict, Any, List
import time
import json
import os
from pathlib import Path

# Import existing NeuroShield components
from langgraph_core.firewall_graph import build_firewall_graph, State
from utils.patterns import KEYWORD_PATTERNS, REGEX_PATTERNS, SECRET_PATTERNS
import re
import math
from collections import defaultdict

app = FastAPI(
    title="NeuroShield API",
    description="Enterprise-grade LLM security platform with prompt firewall and document scanning",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include async endpoints
app.include_router(async_router)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class PromptAnalysisRequest(BaseModel):
    prompt: str = Field(..., description="The user prompt to analyze")
    llm_response: Optional[str] = Field(None, description="Optional existing LLM response for verification")
    
class PromptAnalysisResponse(BaseModel):
    classification: str = Field(..., description="Security classification: Safe, Risky, or Blocked")
    risk_score: float = Field(..., description="Risk score between 0.0 and 1.0")
    reason: str = Field(..., description="Explanation for the classification")
    final_prompt: Optional[str] = Field(None, description="Rewritten safe prompt if applicable")
    llm_response: Optional[str] = Field(None, description="LLM response if generated")
    verdict: Optional[str] = Field(None, description="Response verification verdict")
    attack_detection: Dict[str, Any] = Field(default_factory=dict, description="Detected attack vectors")
    analysis_time: float = Field(..., description="Time taken for analysis in seconds")
    audit_id: str = Field(..., description="Unique audit trail identifier")

class DocumentScanRequest(BaseModel):
    filename: str = Field(..., description="Name of the document")
    content: str = Field(..., description="Text content of the document")

class DocumentScanResponse(BaseModel):
    filename: str = Field(..., description="Name of the scanned document")
    is_safe: bool = Field(..., description="Whether document is safe (no sensitive data)")
    sensitive_patterns: Dict[str, int] = Field(default_factory=dict, description="Detected sensitive patterns and counts")
    scan_time: float = Field(..., description="Time taken for scanning in seconds")
    report_id: str = Field(..., description="Unique scan report identifier")

class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")
    components: Dict[str, str] = Field(default_factory=dict, description="Component health status")

# Global firewall graph instance
firewall_graph = None

def get_firewall_graph():
    """Get or create firewall graph instance"""
    global firewall_graph
    if firewall_graph is None:
        firewall_graph = build_firewall_graph()
    return firewall_graph

def calculate_shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy for randomness detection"""
    if not data:
        return 0.0
    entropy = 0.0
    for x in range(256):
        p_x = float(data.count(chr(x))) / len(data)
        if p_x > 0:
            entropy += -p_x * math.log2(p_x)
    return entropy

def analyze_document_patterns(text: str) -> Dict[str, int]:
    """Analyze text for sensitive patterns"""
    results = defaultdict(int)
    
    # Regex and Secret patterns
    for pattern_name, pattern_regex in {**REGEX_PATTERNS, **SECRET_PATTERNS}.items():
        flags = re.IGNORECASE
        if "Private Key" in pattern_name:
            flags |= re.DOTALL
        if "Generic Secret" in pattern_name:
            flags |= re.VERBOSE
        try:
            matches = re.findall(pattern_regex, text, flags)
            if matches:
                key_name = f"SECRET: {pattern_name}" if pattern_name in SECRET_PATTERNS else pattern_name
                results[key_name] += len(matches)
        except re.error:
            continue
    
    # Entropy analysis for high-entropy strings
    potential_secrets = re.split(r'[\s\'".,;=()\[\]{}]', text)
    high_entropy_strings = sum(
        1 for s in potential_secrets
        if 20 <= len(s) <= 64 and s.isalnum() and calculate_shannon_entropy(s) > 4.5
    )
    if high_entropy_strings > 0:
        results["SECRET: High-Entropy String"] += high_entropy_strings
    
    return dict(results)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test firewall graph initialization
        graph = get_firewall_graph()
        graph_status = "healthy" if graph else "unhealthy"
        
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            components={
                "firewall_graph": graph_status,
                "api": "healthy"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/api/v1/analyze-prompt", response_model=PromptAnalysisResponse)
async def analyze_prompt(request: PromptAnalysisRequest):
    """Analyze prompt for security threats and generate safe alternatives"""
    start_time = time.perf_counter()
    
    try:
        graph = get_firewall_graph()
        
        # Build initial state
        initial_state: State = {"user_prompt": request.prompt}
        if request.llm_response:
            initial_state["llm_response"] = request.llm_response
        
        # Process through firewall graph
        current_state: State = initial_state.copy()
        
        for event in graph.stream(initial_state):
            if not isinstance(event, dict) or not event:
                continue
                
            if "__node__" in event and len(event) == 1:
                continue
            else:
                node_name = list(event.keys())[0]
                payload = event[node_name]
                if payload:
                    current_state.update(payload)
        
        analysis_time = time.perf_counter() - start_time
        audit_id = f"audit_{int(time.time() * 1000)}"
        
        return PromptAnalysisResponse(
            classification=current_state.get("classification", "Unknown"),
            risk_score=current_state.get("risk_score", 0.0),
            reason=current_state.get("reason", "No reason provided"),
            final_prompt=current_state.get("final_prompt"),
            llm_response=current_state.get("llm_response"),
            verdict=current_state.get("verdict"),
            attack_detection=current_state.get("attack_detection", {}),
            analysis_time=analysis_time,
            audit_id=audit_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/v1/scan-document", response_model=DocumentScanResponse)
async def scan_document(request: DocumentScanRequest):
    """Scan document content for sensitive information"""
    start_time = time.perf_counter()
    
    try:
        pattern_results = analyze_document_patterns(request.content)
        sensitive_patterns = {k: v for k, v in pattern_results.items() if k.startswith("SECRET:")}
        
        scan_time = time.perf_counter() - start_time
        report_id = f"scan_{int(time.time() * 1000)}"
        
        return DocumentScanResponse(
            filename=request.filename,
            is_safe=len(sensitive_patterns) == 0,
            sensitive_patterns=sensitive_patterns,
            scan_time=scan_time,
            report_id=report_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document scan failed: {str(e)}")

@app.post("/api/v1/upload-scan-document")
async def upload_and_scan_document(file: UploadFile = File(...)):
    """Upload and scan document file for sensitive information"""
    start_time = time.perf_counter()
    
    try:
        # Read file content
        content = await file.read()
        
        # Extract text based on file type
        if file.filename.endswith('.txt'):
            text_content = content.decode('utf-8')
        elif file.filename.endswith('.pdf'):
            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            text_content = "".join([page.get_text() for page in doc])
        elif file.filename.endswith('.docx'):
            import docx
            import io
            doc = docx.Document(io.BytesIO(content))
            text_content = "\n".join([para.text for para in doc.paragraphs])
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF, DOCX, and TXT are supported.")
        
        # Analyze patterns
        pattern_results = analyze_document_patterns(text_content)
        sensitive_patterns = {k: v for k, v in pattern_results.items() if k.startswith("SECRET:")}
        
        scan_time = time.perf_counter() - start_time
        report_id = f"upload_scan_{int(time.time() * 1000)}"
        
        return DocumentScanResponse(
            filename=file.filename,
            is_safe=len(sensitive_patterns) == 0,
            sensitive_patterns=sensitive_patterns,
            scan_time=scan_time,
            report_id=report_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload and scan failed: {str(e)}")

@app.get("/api/v1/audit-logs")
async def get_audit_logs(limit: int = 100, offset: int = 0):
    """Retrieve audit logs with pagination"""
    try:
        audit_file = Path("logs/audit_log.json")
        if not audit_file.exists():
            return {"logs": [], "total": 0, "limit": limit, "offset": offset}
        
        with open(audit_file, 'r') as f:
            logs = json.load(f)
        
        # Apply pagination
        total = len(logs)
        paginated_logs = logs[offset:offset + limit]
        
        return {
            "logs": paginated_logs,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve audit logs: {str(e)}")

@app.get("/api/v1/statistics")
async def get_statistics():
    """Get security statistics and metrics"""
    try:
        audit_file = Path("logs/audit_log.json")
        if not audit_file.exists():
            return {
                "total_requests": 0,
                "blocked_requests": 0,
                "risky_requests": 0,
                "safe_requests": 0,
                "average_risk_score": 0.0
            }
        
        with open(audit_file, 'r') as f:
            logs = json.load(f)
        
        total = len(logs)
        blocked = sum(1 for log in logs if log.get("classification") == "Blocked")
        risky = sum(1 for log in logs if log.get("classification") == "Risky")
        safe = sum(1 for log in logs if log.get("classification") == "Safe")
        
        # Calculate average risk score (assuming risk_score field exists)
        risk_scores = [log.get("risk_score", 0) for log in logs if "risk_score" in log]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
        
        return {
            "total_requests": total,
            "blocked_requests": blocked,
            "risky_requests": risky,
            "safe_requests": safe,
            "average_risk_score": round(avg_risk, 3)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
