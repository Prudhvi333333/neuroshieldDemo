from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import time
import json
from datetime import datetime
import asyncio
import sys
import os

# Add the parent directory to sys.path to import from langgraph_core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph_core.firewall_graph import build_firewall_graph, State
from ml_engines.performance_optimizer import FastAnalysisEngine, OptimizationLevel

app = FastAPI(
    title="NeuroShield API",
    description="Enterprise AI Security Platform - POC Version",
    version="1.0.0"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for POC (replace with database later)
analysis_results = {}
audit_logs = []

# Initialize performance-optimized analysis engine
fast_engine = FastAnalysisEngine()

# Pydantic models
class AnalysisRequest(BaseModel):
    prompt: str
    user_id: Optional[str] = "anonymous"
    llm_response: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class AnalysisResponse(BaseModel):
    analysis_id: str
    final_decision: str
    risk_score: float
    analysis_time: float
    attack_detection: Dict[str, Any]
    reason: str
    safe_prompt: Optional[str] = ""
    llm_response: Optional[str] = ""
    timestamp: str
    user_id: Optional[str] = "anonymous"
    metadata: Optional[Dict[str, Any]] = {}
    status: str = "completed"

class SIEMEvent(BaseModel):
    event_id: str
    timestamp: str
    event_type: str
    severity: str
    source: str
    description: str
    user_id: str
    threat_indicators: Dict[str, Any]

@app.get("/")
async def root():
    return {
        "message": "NeuroShield API - Enterprise AI Security Platform",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "analysis": "/api/v1/analysis/scan",
            "results": "/api/v1/analysis/{analysis_id}",
            "health": "/api/v1/health",
            "siem": "/api/v1/siem/events"
        }
    }

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "active_analyses": len(analysis_results),
        "total_audit_logs": len(audit_logs)
    }

@app.post("/api/v1/analysis/scan", response_model=AnalysisResponse)
async def analyze_prompt(request: AnalysisRequest, background_tasks: BackgroundTasks):
    analysis_id = str(uuid.uuid4())
    start_time = time.perf_counter()
    
    try:
        # Use optimized analysis engine for <200ms performance
        user_risk_profile = request.metadata.get("risk_profile", "normal")
        
        # Run optimized analysis
        optimized_result = await fast_engine.analyze_optimized(
            prompt=request.prompt,
            llm_response=request.llm_response,
            user_risk_profile=user_risk_profile
        )
        
        analysis_time = time.perf_counter() - start_time
        
        # Extract results from optimized engine
        final_decision = optimized_result.get("final_decision", "Safe")
        risk_score = optimized_result.get("risk_score", 0.0)
        confidence = optimized_result.get("confidence", 0.5)
        method = optimized_result.get("method", "unknown")
        optimization_level = optimized_result.get("optimization_level", "balanced")
        
        # Build attack detection summary
        attack_detection = {
            "method_used": method,
            "optimization_level": optimization_level,
            "confidence": confidence,
            "processing_time": optimized_result.get("processing_time", analysis_time)
        }
        
        # Add component scores if available
        if "component_scores" in optimized_result:
            attack_detection["component_scores"] = optimized_result["component_scores"]
        
        if "pattern_scores" in optimized_result:
            attack_detection["pattern_scores"] = optimized_result["pattern_scores"]
        
        # Add hybrid/attention results if available
        if "hybrid_result" in optimized_result:
            attack_detection["hybrid_analysis"] = optimized_result["hybrid_result"]
        
        if "attention_result" in optimized_result:
            attack_detection["attention_analysis"] = optimized_result["attention_result"]
        
        # Generate reason based on decision and method
        if final_decision == "Blocked":
            reason = f"High risk detected via {method} (score: {risk_score:.2f})"
        elif final_decision == "Risky":
            reason = f"Moderate risk detected via {method} (score: {risk_score:.2f})"
        else:
            reason = f"Content appears safe via {method} (score: {risk_score:.2f})"
        
        # Prepare response
        response = AnalysisResponse(
            analysis_id=analysis_id,
            final_decision=final_decision,
            risk_score=risk_score,
            analysis_time=analysis_time,
            attack_detection=attack_detection,
            reason=reason,
            timestamp=datetime.now().isoformat(),
            user_id=request.user_id,
            metadata=request.metadata
        )
        
        # Store result
        analysis_results[analysis_id] = response.dict()
        
        # Background tasks for audit logging and SIEM events
        background_tasks.add_task(log_audit_event, analysis_id, request, response)
        background_tasks.add_task(generate_siem_event, analysis_id, request, response)
        
        return response
        
    except Exception as e:
        # Fallback to original analysis if optimization fails
        try:
            # Build the firewall graph as fallback
            graph = build_firewall_graph()
            
            # Prepare initial state
            initial_graph_state: State = {
                "user_prompt": request.prompt
            }
            
            if request.llm_response:
                initial_graph_state["llm_response"] = request.llm_response
            
            # Stream through the graph and accumulate state
            current_accumulated_state: State = initial_graph_state.copy()
            
            for event in graph.stream(initial_graph_state):
                if not isinstance(event, dict) or not event:
                    continue
                
                # Skip node-only events
                if "__node__" in event and len(event) == 1:
                    continue
                else:
                    # Extract the actual payload
                    node_name = list(event.keys())[0]
                    payload = event[node_name]
                    
                    if payload:
                        current_accumulated_state.update(payload)
            
            analysis_time = time.perf_counter() - start_time
            
            # Extract results from accumulated state
            final_decision = current_accumulated_state.get("final_decision", "Safe")
            risk_score = current_accumulated_state.get("risk_score", 0.0)
            attack_detection = current_accumulated_state.get("attack_detection", {})
            attack_detection["fallback_used"] = True
            attack_detection["optimization_error"] = str(e)
            reason = current_accumulated_state.get("reason", "Analysis completed via fallback")
            
            # Prepare response
            response = AnalysisResponse(
                analysis_id=analysis_id,
                final_decision=final_decision,
                risk_score=risk_score,
                analysis_time=analysis_time,
                attack_detection=attack_detection,
                reason=reason,
                timestamp=datetime.now().isoformat(),
                user_id=request.user_id,
                metadata=request.metadata
            )
            
            # Store result
            analysis_results[analysis_id] = response.dict()
            
            # Background tasks for audit logging and SIEM events
            background_tasks.add_task(log_audit_event, analysis_id, request, response)
            background_tasks.add_task(generate_siem_event, analysis_id, request, response)
            
            return response
            
        except Exception as fallback_error:
            # Final error response
            analysis_time = time.perf_counter() - start_time
            error_response = AnalysisResponse(
                analysis_id=analysis_id,
                final_decision="Error",
                risk_score=0.0,
                analysis_time=analysis_time,
                attack_detection={"error": str(fallback_error), "optimization_error": str(e)},
                reason=f"Analysis failed: {str(fallback_error)}",
                timestamp=datetime.now().isoformat(),
                user_id=request.user_id,
                metadata=request.metadata
            )
            
            analysis_results[analysis_id] = error_response.dict()
            return error_response

@app.get("/api/v1/analysis/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis_result(analysis_id: str):
    """
    Retrieve analysis results by ID
    """
    if analysis_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    result = analysis_results[analysis_id]
    return AnalysisResponse(**result)

@app.get("/api/v1/analysis")
async def list_analyses(limit: int = 10, offset: int = 0):
    """
    List recent analyses with pagination
    """
    all_analyses = list(analysis_results.values())
    # Sort by timestamp (most recent first)
    sorted_analyses = sorted(
        all_analyses, 
        key=lambda x: x['timestamp'], 
        reverse=True
    )
    
    paginated = sorted_analyses[offset:offset + limit]
    
    return {
        "analyses": paginated,
        "total": len(all_analyses),
        "limit": limit,
        "offset": offset
    }

@app.get("/api/v1/siem/events")
async def get_siem_events(limit: int = 50):
    """
    Get SIEM-formatted security events
    """
    # Filter audit logs for security events
    security_events = [
        log for log in audit_logs 
        if log.get("event_type") == "security_threat"
    ]
    
    return {
        "events": security_events[-limit:],  # Most recent events
        "total": len(security_events),
        "format": "OCSF-compatible"
    }

@app.post("/api/v1/siem/webhook")
async def siem_webhook_endpoint(event_data: Dict[str, Any]):
    """
    Webhook endpoint for SIEM integration
    """
    # Process incoming SIEM data
    processed_event = {
        "received_at": datetime.utcnow().isoformat(),
        "source": "external_siem",
        "data": event_data
    }
    
    audit_logs.append(processed_event)
    
    return {"status": "received", "event_id": str(uuid.uuid4())}

@app.get("/api/v1/performance/stats")
async def get_performance_stats():
    """
    Get performance statistics from the optimized analysis engine
    """
    try:
        stats = fast_engine.get_performance_stats()
        return {
            "performance_metrics": stats,
            "target_latency": "200ms",
            "optimization_enabled": True,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "performance_metrics": None,
            "optimization_enabled": False
        }

@app.get("/api/v1/stats")
async def get_statistics():
    """
    Get platform statistics
    """
    total_analyses = len(analysis_results)
    
    # Calculate threat statistics
    threat_counts = {"Safe": 0, "Risky": 0, "Blocked": 0, "Unknown": 0, "Error": 0}
    total_risk_score = 0
    
    for result in analysis_results.values():
        decision = result.get("final_decision", "Unknown")
        threat_counts[decision] = threat_counts.get(decision, 0) + 1
        total_risk_score += result.get("risk_score", 0)
    
    avg_risk_score = total_risk_score / total_analyses if total_analyses > 0 else 0
    
    return {
        "total_analyses": total_analyses,
        "threat_distribution": threat_counts,
        "average_risk_score": round(avg_risk_score, 3),
        "security_events": len([log for log in audit_logs if log.get("event_type") == "security_threat"]),
        "uptime": "active"
    }

# Background task functions
async def log_analysis_event(analysis_id: str, user_id: str, prompt: str, decision: str, risk_score: float):
    """Log analysis event to audit trail"""
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "analysis_completed",
        "analysis_id": analysis_id,
        "user_id": user_id,
        "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,  # Truncate for privacy
        "classification": decision,
        "risk_score": risk_score,
        "source": "neuroshield_api"
    }
    audit_logs.append(audit_entry)

async def generate_siem_event(analysis_id: str, user_id: str, decision: str, risk_score: float, attack_detection: Dict):
    """Generate SIEM-compatible security event"""
    
    # Determine severity based on risk score
    if risk_score >= 0.8:
        severity = "high"
    elif risk_score >= 0.5:
        severity = "medium"
    else:
        severity = "low"
    
    siem_event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "security_threat",
        "event_id": str(uuid.uuid4()),
        "analysis_id": analysis_id,
        "severity": severity,
        "source": "neuroshield_ai_firewall",
        "user_id": user_id,
        "threat_classification": decision,
        "risk_score": risk_score,
        "attack_indicators": attack_detection,
        "description": f"AI security threat detected: {decision} (Risk: {risk_score:.2f})",
        "ocsf_category": "security_finding",
        "ocsf_class": "detection_finding"
    }
    
    audit_logs.append(siem_event)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
