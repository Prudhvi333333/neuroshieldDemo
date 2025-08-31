"""
Async agent manager for parallel processing of LLM-dependent tasks
Reduces analysis time by running agents concurrently instead of sequentially
"""
import asyncio
import time
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.initial_analysis_agent import InitialAnalysisAgent
try:
    from agents.response_verifier_agent import ResponseVerifierAgent
except ImportError:
    ResponseVerifierAgent = None
try:
    from agents.web_search_agent import WebSearchAgent  
except ImportError:
    WebSearchAgent = None

class AsyncAgentManager:
    """Manages parallel execution of agents for faster processing"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Initialize agents
        self.initial_agent = InitialAnalysisAgent()
        self.verifier_agent = ResponseVerifierAgent() if ResponseVerifierAgent else None
        self.web_search_agent = WebSearchAgent() if WebSearchAgent else None
    
    async def analyze_prompt_async(self, prompt: str, llm_response: str = None) -> Dict[str, Any]:
        """
        Async analysis with parallel agent execution
        Only uses LLM for complex cases that bypass Layer 1-2
        """
        start_time = time.perf_counter()
        
        # Step 1: Initial analysis (required)
        initial_result = await self._run_agent_async(self.initial_agent.run, prompt)
        
        # If high confidence from Layer 1-2, skip verification
        if initial_result.get("fast_classification") or initial_result.get("advanced_classification"):
            analysis_time = time.perf_counter() - start_time
            initial_result["analysis_time"] = analysis_time
            return initial_result
        
        # Step 2: For LLM-analyzed prompts, run verification in parallel if response provided
        tasks = []
        
        if llm_response and self.verifier_agent:
            # Run verification in parallel
            tasks.append(self._run_agent_async(self.verifier_agent.run, prompt, llm_response))
            
            # Only run web search if available and verification might be needed
            if self.web_search_agent and initial_result.get("risk_score", 0) > 0.3:
                tasks.append(self._run_agent_async(self.web_search_agent.run, prompt))
        
        # Execute parallel tasks
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process verification result
            if len(results) > 0 and not isinstance(results[0], Exception):
                verification_result = results[0]
                initial_result.update(verification_result)
            
            # Process web search result if available
            if len(results) > 1 and not isinstance(results[1], Exception):
                web_result = results[1]
                initial_result.update(web_result)
        
        analysis_time = time.perf_counter() - start_time
        initial_result["analysis_time"] = analysis_time
        initial_result["async_processing"] = True
        
        return initial_result
    
    async def _run_agent_async(self, agent_func, *args) -> Dict[str, Any]:
        """Run agent function asynchronously"""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(self.executor, agent_func, *args)
            return result if result else {}
        except Exception as e:
            logging.warning(f"Async agent execution failed: {e}")
            return {"error": str(e)}
    
    def analyze_batch_async(self, prompts: List[str]) -> List[Dict[str, Any]]:
        """Analyze multiple prompts in parallel"""
        async def batch_analysis():
            tasks = [self.analyze_prompt_async(prompt) for prompt in prompts]
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        return asyncio.run(batch_analysis())
    
    def __del__(self):
        """Cleanup executor on destruction"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)

# Global async manager instance
async_manager = AsyncAgentManager(max_workers=3)
