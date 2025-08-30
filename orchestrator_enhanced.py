#!/usr/bin/env python3
"""
Enhanced Agent Orchestration System - Day 5 Implementation
Centralized coordination and management of all NeuroShield agents
"""

import asyncio
import time
import json
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import concurrent.futures
from contextlib import asynccontextmanager

# Import all agents
from agents.enhanced_firewall_agent import EnhancedFirewallAgent
from agents.shadow_ai_agent import ShadowAIDetectionAgent
from agents.behavioral_analytics_agent import BehavioralAnalyticsAgent
from agents.threat_intelligence_agent import ThreatIntelligenceAgent
from agents.attack_detection_agent import AttackDetectionAgent
from agents.audit_chain_agent import AuditChainAgent

class OrchestrationStrategy(Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    PRIORITY_BASED = "priority_based"
    ADAPTIVE = "adaptive"
    FAST = "fast"
    BALANCED = "balanced"

class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"

@dataclass
class AgentMetrics:
    agent_name: str
    total_executions: int
    avg_response_time: float
    success_rate: float
    last_execution: Optional[datetime]
    error_count: int
    status: AgentStatus

@dataclass
class OrchestrationResult:
    request_id: str
    strategy_used: OrchestrationStrategy
    total_processing_time: float
    agent_results: Dict[str, Any]
    final_decision: Dict[str, Any]
    metrics: Dict[str, AgentMetrics]
    timestamp: datetime

class EnhancedAgentOrchestrator:
    """
    Advanced orchestration system for coordinating multiple security agents
    
    Features:
    - Multiple orchestration strategies
    - Agent health monitoring and failover
    - Load balancing and performance optimization
    - Centralized logging and metrics
    - Adaptive routing based on agent performance
    """
    
    def __init__(self):
        # Configure logging first
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.agents = {}
        self.agent_metrics = {}
        self.orchestration_history = []
        self.max_concurrent_agents = 5
        self.timeout_seconds = 30
        
        # Initialize agents after logger is set up
        self._initialize_agents()
        
        self.logger.info("Enhanced Agent Orchestrator initialized")
    
    def _initialize_agents(self):
        """Initialize all available agents with health monitoring"""
        agent_configs = {
            "enhanced_firewall": {
                "class": EnhancedFirewallAgent,
                "priority": 1,
                "timeout": 10,
                "retry_count": 2
            },
            "shadow_ai_detection": {
                "class": ShadowAIDetectionAgent,
                "priority": 2,
                "timeout": 15,
                "retry_count": 1
            },
            "behavioral_analytics": {
                "class": BehavioralAnalyticsAgent,
                "priority": 3,
                "timeout": 20,
                "retry_count": 1
            },
            "threat_intelligence": {
                "class": ThreatIntelligenceAgent,
                "priority": 2,
                "timeout": 10,
                "retry_count": 2
            },
            "attack_detection": {
                "class": AttackDetectionAgent,
                "priority": 3,
                "timeout": 15,
                "retry_count": 1
            },
            "audit_chain": {
                "class": AuditChainAgent,
                "priority": 4,
                "timeout": 5,
                "retry_count": 1
            }
        }
        
        for agent_name, config in agent_configs.items():
            try:
                agent_instance = config["class"]()
                self.agents[agent_name] = {
                    "instance": agent_instance,
                    "config": config,
                    "status": AgentStatus.IDLE
                }
                
                # Initialize metrics
                self.agent_metrics[agent_name] = AgentMetrics(
                    agent_name=agent_name,
                    total_executions=0,
                    avg_response_time=0.0,
                    success_rate=1.0,
                    last_execution=None,
                    error_count=0,
                    status=AgentStatus.IDLE
                )
                
                self.logger.info(f"Initialized agent: {agent_name}")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize agent {agent_name}: {e}")
                if agent_name in self.agents:
                    self.agents[agent_name]["status"] = AgentStatus.ERROR
    
    async def orchestrate_analysis(
        self, 
        prompt: str, 
        context: Dict[str, Any] = None,
        strategy: OrchestrationStrategy = OrchestrationStrategy.ADAPTIVE,
        agent_filter: List[str] = None
    ) -> OrchestrationResult:
        """
        Orchestrate analysis across multiple agents using specified strategy
        """
        request_id = f"req_{int(time.time())}_{hash(prompt) % 10000}"
        start_time = time.time()
        
        self.logger.info(f"Starting orchestrated analysis {request_id} with strategy: {strategy.value}")
        
        # Filter agents if specified
        active_agents = self._get_active_agents(agent_filter)
        
        # Execute based on strategy
        if strategy == OrchestrationStrategy.PARALLEL:
            agent_results = await self._execute_parallel(active_agents, prompt, context)
        elif strategy == OrchestrationStrategy.SEQUENTIAL:
            agent_results = await self._execute_sequential(active_agents, prompt, context)
        elif strategy == OrchestrationStrategy.PRIORITY_BASED:
            agent_results = await self._execute_priority_based(active_agents, prompt, context)
        else:  # ADAPTIVE
            agent_results = await self._execute_adaptive(active_agents, prompt, context)
        
        # Aggregate results and make final decision
        final_decision = self._aggregate_results(agent_results)
        
        # Update metrics
        self._update_metrics(agent_results)
        
        # Create orchestration result
        result = OrchestrationResult(
            request_id=request_id,
            strategy_used=strategy,
            total_processing_time=time.time() - start_time,
            agent_results=agent_results,
            final_decision=final_decision,
            metrics={name: asdict(metrics) for name, metrics in self.agent_metrics.items()},
            timestamp=datetime.now()
        )
        
        self.orchestration_history.append(result)
        
        self.logger.info(f"Completed orchestrated analysis {request_id} in {result.total_processing_time:.3f}s")
        
        return result
    
    def _get_active_agents(self, agent_filter: List[str] = None) -> Dict[str, Any]:
        """Get active agents based on filter and health status"""
        active_agents = {}
        
        for agent_name, agent_data in self.agents.items():
            # Apply filter if specified
            if agent_filter and agent_name not in agent_filter:
                continue
            
            # Check agent health
            if agent_data["status"] in [AgentStatus.IDLE, AgentStatus.RUNNING]:
                active_agents[agent_name] = agent_data
        
        return active_agents
    
    async def _execute_parallel(self, agents: Dict[str, Any], prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all agents in parallel"""
        tasks = []
        agent_names = []
        
        for agent_name, agent_data in agents.items():
            task = self._execute_agent_with_timeout(agent_name, agent_data, prompt, context)
            tasks.append(task)
            agent_names.append(agent_name)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        agent_results = {}
        for i, result in enumerate(results):
            agent_name = agent_names[i]
            if isinstance(result, Exception):
                agent_results[agent_name] = {"error": str(result), "status": "failed"}
            else:
                agent_results[agent_name] = result
        
        return agent_results
    
    async def _execute_sequential(self, agents: Dict[str, Any], prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agents sequentially based on priority"""
        agent_results = {}
        
        # Sort agents by priority
        sorted_agents = sorted(agents.items(), key=lambda x: x[1]["config"]["priority"])
        
        for agent_name, agent_data in sorted_agents:
            try:
                result = await self._execute_agent_with_timeout(agent_name, agent_data, prompt, context)
                agent_results[agent_name] = result
                
                # Check if we should stop based on result
                if self._should_stop_sequential(result):
                    break
                    
            except Exception as e:
                agent_results[agent_name] = {"error": str(e), "status": "failed"}
        
        return agent_results
    
    async def _execute_priority_based(self, agents: Dict[str, Any], prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute high-priority agents first, then others in parallel"""
        high_priority_agents = {name: data for name, data in agents.items() 
                              if data["config"]["priority"] <= 2}
        low_priority_agents = {name: data for name, data in agents.items() 
                             if data["config"]["priority"] > 2}
        
        agent_results = {}
        
        # Execute high-priority agents first
        if high_priority_agents:
            high_priority_results = await self._execute_parallel(high_priority_agents, prompt, context)
            agent_results.update(high_priority_results)
        
        # Execute low-priority agents in parallel
        if low_priority_agents:
            low_priority_results = await self._execute_parallel(low_priority_agents, prompt, context)
            agent_results.update(low_priority_results)
        
        return agent_results
    
    async def _execute_adaptive(self, agents: Dict[str, Any], prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Adaptive execution based on agent performance and content analysis"""
        # Analyze prompt to determine optimal strategy
        prompt_analysis = self._analyze_prompt_complexity(prompt)
        
        if prompt_analysis["complexity"] == "high":
            return await self._execute_parallel(agents, prompt, context)
        elif prompt_analysis["risk_indicators"]:
            return await self._execute_priority_based(agents, prompt, context)
        else:
            # Use fastest agents first for simple queries
            fast_agents = {name: data for name, data in agents.items() 
                          if self.agent_metrics[name].avg_response_time < 1.0}
            if fast_agents:
                return await self._execute_parallel(fast_agents, prompt, context)
            else:
                return await self._execute_sequential(agents, prompt, context)
    
    async def _execute_agent_with_timeout(self, agent_name: str, agent_data: Dict[str, Any], 
                                        prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single agent with timeout and retry logic"""
        agent_instance = agent_data["instance"]
        timeout = agent_data["config"]["timeout"]
        retry_count = agent_data["config"]["retry_count"]
        
        for attempt in range(retry_count + 1):
            try:
                # Update agent status
                self.agents[agent_name]["status"] = AgentStatus.RUNNING
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    agent_instance.execute(prompt, context),
                    timeout=timeout
                )
                
                # Update agent status
                self.agents[agent_name]["status"] = AgentStatus.IDLE
                
                return result
                
            except asyncio.TimeoutError:
                self.logger.warning(f"Agent {agent_name} timed out (attempt {attempt + 1})")
                if attempt == retry_count:
                    self.agents[agent_name]["status"] = AgentStatus.ERROR
                    raise
            except Exception as e:
                self.logger.error(f"Agent {agent_name} failed (attempt {attempt + 1}): {e}")
                if attempt == retry_count:
                    self.agents[agent_name]["status"] = AgentStatus.ERROR
                    raise
        
        # This should never be reached, but just in case
        raise Exception(f"Agent {agent_name} failed after all retry attempts")
    
    def _should_stop_sequential(self, result: Dict[str, Any]) -> bool:
        """Determine if sequential execution should stop based on result"""
        # Stop if we get a high-confidence block decision
        if isinstance(result, dict):
            security_decision = result.get("security_decision", {})
            if (security_decision.get("action") == "block" and 
                security_decision.get("confidence", 0) > 0.8):
                return True
        return False
    
    def _analyze_prompt_complexity(self, prompt: str) -> Dict[str, Any]:
        """Analyze prompt to determine complexity and risk indicators"""
        risk_keywords = ["inject", "bypass", "hack", "exploit", "malicious", "attack"]
        complex_patterns = ["multi-step", "complex", "analyze", "detailed"]
        
        risk_indicators = any(keyword in prompt.lower() for keyword in risk_keywords)
        complexity_indicators = any(pattern in prompt.lower() for pattern in complex_patterns)
        
        complexity = "high" if len(prompt) > 500 or complexity_indicators else "low"
        
        return {
            "complexity": complexity,
            "risk_indicators": risk_indicators,
            "length": len(prompt)
        }
    
    def _aggregate_results(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate results from multiple agents into final decision"""
        # Collect all security decisions
        security_decisions = []
        risk_scores = []
        threat_categories = set()
        
        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and "error" not in result:
                # Extract security decision
                if "security_decision" in result:
                    security_decisions.append(result["security_decision"])
                    risk_scores.append(result["security_decision"].get("risk_score", 0))
                    threat_categories.update(result["security_decision"].get("threat_categories", []))
                
                # Extract other risk indicators
                if "shadow_ai_event" in result:
                    event = result["shadow_ai_event"]
                    risk_scores.append(event.get("confidence", 0))
                
                if "composite_anomaly_score" in result:
                    risk_scores.append(result["composite_anomaly_score"])
        
        # Determine final action based on aggregated results
        if not risk_scores:
            final_action = "allow"
            final_risk = 0.0
        else:
            max_risk = max(risk_scores)
            avg_risk = sum(risk_scores) / len(risk_scores)
            final_risk = max(max_risk, avg_risk)  # Use higher of max or average
            
            # Determine action based on risk
            if final_risk >= 0.8:
                final_action = "block"
            elif final_risk >= 0.6:
                final_action = "quarantine"
            elif final_risk >= 0.4:
                final_action = "monitor"
            else:
                final_action = "allow"
        
        return {
            "final_action": final_action,
            "final_risk_score": final_risk,
            "threat_categories": list(threat_categories),
            "agent_count": len([r for r in agent_results.values() if "error" not in r]),
            "consensus_strength": len(security_decisions),
            "processing_summary": {
                "total_agents": len(agent_results),
                "successful_agents": len([r for r in agent_results.values() if "error" not in r]),
                "failed_agents": len([r for r in agent_results.values() if "error" in r])
            }
        }
    
    def _update_metrics(self, agent_results: Dict[str, Any]):
        """Update agent performance metrics"""
        for agent_name, result in agent_results.items():
            if agent_name in self.agent_metrics:
                metrics = self.agent_metrics[agent_name]
                
                # Update execution count
                metrics.total_executions += 1
                
                # Update success rate
                if "error" in result:
                    metrics.error_count += 1
                
                metrics.success_rate = (metrics.total_executions - metrics.error_count) / metrics.total_executions
                
                # Update response time (if available)
                if isinstance(result, dict) and "processing_time" in result:
                    processing_time = result["processing_time"]
                    if metrics.avg_response_time == 0:
                        metrics.avg_response_time = processing_time
                    else:
                        # Exponential moving average
                        metrics.avg_response_time = 0.7 * metrics.avg_response_time + 0.3 * processing_time
                
                # Update last execution
                metrics.last_execution = datetime.now()
    
    def get_orchestration_stats(self) -> Dict[str, Any]:
        """Get comprehensive orchestration statistics"""
        return {
            "total_orchestrations": len(self.orchestration_history),
            "agent_metrics": {name: asdict(metrics) for name, metrics in self.agent_metrics.items()},
            "agent_status": {name: data["status"].value for name, data in self.agents.items()},
            "recent_performance": self._get_recent_performance_stats(),
            "system_health": self._get_system_health()
        }
    
    def _get_recent_performance_stats(self) -> Dict[str, Any]:
        """Get recent performance statistics"""
        if not self.orchestration_history:
            return {}
        
        recent_results = self.orchestration_history[-10:]  # Last 10 orchestrations
        
        avg_processing_time = sum(r.total_processing_time for r in recent_results) / len(recent_results)
        strategy_usage = {}
        
        for result in recent_results:
            strategy = result.strategy_used.value
            strategy_usage[strategy] = strategy_usage.get(strategy, 0) + 1
        
        return {
            "avg_processing_time": avg_processing_time,
            "strategy_usage": strategy_usage,
            "recent_orchestrations": len(recent_results)
        }
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        total_agents = len(self.agents)
        healthy_agents = len([a for a in self.agents.values() if a["status"] != AgentStatus.ERROR])
        
        overall_success_rate = sum(m.success_rate for m in self.agent_metrics.values()) / len(self.agent_metrics)
        
        health_status = "healthy" if healthy_agents == total_agents else "degraded" if healthy_agents > 0 else "critical"
        
        return {
            "status": health_status,
            "healthy_agents": healthy_agents,
            "total_agents": total_agents,
            "overall_success_rate": overall_success_rate,
            "avg_response_time": sum(m.avg_response_time for m in self.agent_metrics.values()) / len(self.agent_metrics)
        }

# Global orchestrator instance
orchestrator = EnhancedAgentOrchestrator()

async def orchestrate_security_analysis(prompt: str, context: Dict[str, Any] = None, 
                                       strategy: str = "adaptive") -> Dict[str, Any]:
    """
    Main entry point for orchestrated security analysis
    """
    strategy_enum = OrchestrationStrategy(strategy.lower())
    result = await orchestrator.orchestrate_analysis(prompt, context, strategy_enum)
    
    return {
        "request_id": result.request_id,
        "final_decision": result.final_decision,
        "processing_time": result.total_processing_time,
        "strategy_used": result.strategy_used.value,
        "agent_results": result.agent_results,
        "timestamp": result.timestamp.isoformat()
    }

if __name__ == "__main__":
    # Test the orchestrator
    async def test_orchestrator():
        test_prompt = "Can you help me analyze this customer database using ChatGPT API?"
        test_context = {
            "network_traffic": {
                "source_ip": "192.168.1.100",
                "destination_ip": "104.18.7.192",
                "domain": "api.openai.com"
            }
        }
        
        result = await orchestrate_security_analysis(test_prompt, test_context, "adaptive")
        print(json.dumps(result, indent=2, default=str))
        
        # Print orchestration stats
        stats = orchestrator.get_orchestration_stats()
        print("\nOrchestration Stats:")
        print(json.dumps(stats, indent=2, default=str))
    
    asyncio.run(test_orchestrator())
