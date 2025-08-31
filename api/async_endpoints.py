"""
Async API endpoints for improved performance
Handles both fast Layer 1-2 classification and optimized LLM processing
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import time

from agents.async_agent_manager import async_manager
from utils.fast_classifier import fast_classifier
from utils.advanced_classifier import advanced_classifier

router = APIRouter(prefix="/api/v2", tags=["async-analysis"])

class AsyncPromptRequest(BaseModel):
    prompt: str
    llm_response: Optional[str] = None
    priority: Optional[str] = "normal"  # "high", "normal", "low"

class AsyncPromptResponse(BaseModel):
    classification: str
    risk_score: float
    reason: str
    analysis_time: float
    processing_path: str
    attack_detection: Dict[str, Any]
    audit_id: str

@router.post("/analyze-prompt-async", response_model=AsyncPromptResponse)
async def analyze_prompt_async(request: AsyncPromptRequest):
    """
    Async prompt analysis with optimized Layer 1-2-3 processing
    Expected performance: 0.1ms (Layer 1-2) or 3-5s (Layer 3)
    """
    start_time = time.perf_counter()
    prompt = request.prompt
    
    try:
        # Layer 1: Fast pattern matching (0.1ms)
        fast_result = fast_classifier.quick_classify(prompt)
        if fast_result:
            analysis_time = time.perf_counter() - start_time
            return AsyncPromptResponse(
                classification=fast_result["classification"],
                risk_score=fast_result["risk_score"],
                reason=fast_result["reason"],
                analysis_time=analysis_time,
                processing_path="Layer1_Pattern",
                attack_detection=fast_result.get("attack_detection", {}),
                audit_id=f"layer1_{int(time.time())}"
            )
        
        # Layer 2: Advanced keyword analysis (0.1ms)
        advanced_result = advanced_classifier.classify_prompt(prompt, risk_threshold=0.4, safe_threshold=0.3)
        if advanced_result:
            analysis_time = time.perf_counter() - start_time
            return AsyncPromptResponse(
                classification=advanced_result["classification"],
                risk_score=advanced_result["risk_score"],
                reason=advanced_result["reason"],
                analysis_time=analysis_time,
                processing_path="Layer2_Advanced",
                attack_detection=advanced_result.get("attack_detection", {}),
                audit_id=f"layer2_{int(time.time())}"
            )
        
        # Layer 3: Async LLM analysis (3-5s optimized)
        llm_result = await async_manager.analyze_prompt_async(prompt, request.llm_response)
        analysis_time = time.perf_counter() - start_time
        
        return AsyncPromptResponse(
            classification=llm_result.get("classification", "Risky"),
            risk_score=llm_result.get("risk_score", 0.8),
            reason=llm_result.get("reason", "Complex analysis completed"),
            analysis_time=analysis_time,
            processing_path="Layer3_LLM_Async",
            attack_detection=llm_result.get("attack_detection", {}),
            audit_id=f"layer3_{int(time.time())}"
        )
        
    except Exception as e:
        analysis_time = time.perf_counter() - start_time
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed after {analysis_time:.2f}s: {str(e)}"
        )

@router.post("/analyze-batch-async")
async def analyze_batch_async(prompts: list[str]):
    """
    Batch analysis with parallel processing
    Optimizes throughput for multiple prompts
    """
    start_time = time.perf_counter()
    
    # Separate prompts by processing layer
    layer1_results = []
    layer2_results = []
    layer3_prompts = []
    
    # Quick classification for all prompts
    for i, prompt in enumerate(prompts):
        # Layer 1 check
        fast_result = fast_classifier.quick_classify(prompt)
        if fast_result:
            fast_result["prompt_index"] = i
            fast_result["processing_path"] = "Layer1_Pattern"
            layer1_results.append(fast_result)
            continue
        
        # Layer 2 check
        advanced_result = advanced_classifier.classify_prompt(prompt)
        if advanced_result:
            advanced_result["prompt_index"] = i
            advanced_result["processing_path"] = "Layer2_Advanced"
            layer2_results.append(advanced_result)
            continue
        
        # Needs LLM analysis
        layer3_prompts.append((i, prompt))
    
    # Process Layer 3 prompts in parallel
    layer3_results = []
    if layer3_prompts:
        llm_tasks = [
            async_manager.analyze_prompt_async(prompt) 
            for _, prompt in layer3_prompts
        ]
        llm_results = await asyncio.gather(*llm_tasks, return_exceptions=True)
        
        for (i, prompt), result in zip(layer3_prompts, llm_results):
            if not isinstance(result, Exception):
                result["prompt_index"] = i
                result["processing_path"] = "Layer3_LLM_Async"
                layer3_results.append(result)
    
    # Combine and sort results
    all_results = layer1_results + layer2_results + layer3_results
    all_results.sort(key=lambda x: x["prompt_index"])
    
    total_time = time.perf_counter() - start_time
    
    return {
        "results": all_results,
        "summary": {
            "total_prompts": len(prompts),
            "layer1_count": len(layer1_results),
            "layer2_count": len(layer2_results), 
            "layer3_count": len(layer3_results),
            "total_analysis_time": total_time,
            "average_time_per_prompt": total_time / len(prompts) if prompts else 0
        }
    }
