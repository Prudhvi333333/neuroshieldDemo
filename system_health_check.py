#!/usr/bin/env python3
"""
NeuroShield System Health Check
Comprehensive testing of all components: ML engines, APIs, orchestration, and integrations
"""

import asyncio
import time
import sys
import traceback
from typing import Dict, List, Any
import json
from datetime import datetime

class SystemHealthChecker:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "UNKNOWN",
            "component_tests": {},
            "performance_metrics": {},
            "errors": [],
            "warnings": []
        }
    
    async def run_comprehensive_check(self):
        """Run all system health checks"""
        print("🔍 Starting NeuroShield System Health Check...")
        print("=" * 60)
        
        # Test 1: Core Imports
        await self.test_core_imports()
        
        # Test 2: ML Engines
        await self.test_ml_engines()
        
        # Test 3: Agent System
        await self.test_agent_system()
        
        # Test 4: Orchestration
        await self.test_orchestration()
        
        # Test 5: API Components
        await self.test_api_components()
        
        # Test 6: Integration Tests
        await self.test_integrations()
        
        # Generate final report
        self.generate_final_report()
        
        return self.results
    
    async def test_core_imports(self):
        """Test all critical imports"""
        print("\n1. Testing Core Imports...")
        test_name = "core_imports"
        start_time = time.perf_counter()
        
        try:
            # Test enhanced orchestrator
            from orchestrator_enhanced import orchestrator, orchestrate_security_analysis, OrchestrationStrategy
            print("   ✅ Enhanced orchestrator imported")
            
            # Test ML engines
            from ml_engines.attention_tracker import AttentionDriftDetector
            from ml_engines.hybrid_ensemble import HybridEnsemble
            from ml_engines.federated_learning_engine import FederatedLearningEngine
            from ml_engines.performance_optimizer import FastAnalysisEngine
            print("   ✅ All ML engines imported")
            
            # Test agents
            from agents.enhanced_firewall_agent import EnhancedFirewallAgent
            from agents.shadow_ai_agent import ShadowAIDetectionAgent
            from agents.behavioral_analytics_agent import BehavioralAnalyticsAgent
            print("   ✅ Enhanced agents imported")
            
            # Test utilities
            from llm_utils import call_llm
            print("   ✅ Utilities imported")
            
            elapsed = time.perf_counter() - start_time
            self.results["component_tests"][test_name] = {
                "status": "PASS",
                "duration": elapsed,
                "details": "All critical imports successful"
            }
            
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            error_msg = f"Import error: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.results["component_tests"][test_name] = {
                "status": "FAIL",
                "duration": elapsed,
                "error": error_msg
            }
            self.results["errors"].append(error_msg)
    
    async def test_ml_engines(self):
        """Test ML engine functionality"""
        print("\n2. Testing ML Engines...")
        test_name = "ml_engines"
        start_time = time.perf_counter()
        
        try:
            # Test Attention Tracker
            print("   Testing Attention Tracker...")
            from ml_engines.attention_tracker import AttentionDriftDetector
            attention_detector = AttentionDriftDetector()
            
            # Test with safe prompt
            safe_result = attention_detector.analyze_prompt("What is machine learning?")
            print(f"   ✅ Attention Tracker - Safe prompt: {safe_result.threat_level.value}")
            
            # Test Performance Optimizer
            print("   Testing Performance Optimizer...")
            from ml_engines.performance_optimizer import FastAnalysisEngine
            optimizer = FastAnalysisEngine()
            
            # Test optimization
            opt_result = await optimizer.analyze_optimized("Test prompt for optimization")
            print(f"   ✅ Performance Optimizer - Method: {opt_result.get('method', 'unknown')}")
            
            # Test Federated Learning Engine
            print("   Testing Federated Learning...")
            from ml_engines.federated_learning_engine import FederatedLearningEngine
            fed_engine = FederatedLearningEngine()
            print("   ✅ Federated Learning Engine initialized")
            
            elapsed = time.perf_counter() - start_time
            self.results["component_tests"][test_name] = {
                "status": "PASS",
                "duration": elapsed,
                "details": "All ML engines functional"
            }
            
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            error_msg = f"ML Engine error: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.results["component_tests"][test_name] = {
                "status": "FAIL",
                "duration": elapsed,
                "error": error_msg
            }
            self.results["errors"].append(error_msg)
    
    async def test_agent_system(self):
        """Test agent system functionality"""
        print("\n3. Testing Agent System...")
        test_name = "agent_system"
        start_time = time.perf_counter()
        
        try:
            from agents.enhanced_firewall_agent import EnhancedFirewallAgent
            from agents.shadow_ai_agent import ShadowAIDetectionAgent
            
            # Test Enhanced Firewall Agent
            firewall_agent = EnhancedFirewallAgent()
            firewall_result = await firewall_agent.execute("Test security prompt", {})
            print(f"   ✅ Enhanced Firewall Agent - Status: {firewall_result.get('status', 'unknown')}")
            
            # Test Shadow AI Agent
            shadow_agent = ShadowAIDetectionAgent()
            shadow_result = await shadow_agent.execute("Test AI detection prompt", {})
            print(f"   ✅ Shadow AI Agent - Status: {shadow_result.get('status', 'unknown')}")
            
            elapsed = time.perf_counter() - start_time
            self.results["component_tests"][test_name] = {
                "status": "PASS",
                "duration": elapsed,
                "details": "Agent system functional"
            }
            
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            error_msg = f"Agent system error: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.results["component_tests"][test_name] = {
                "status": "FAIL",
                "duration": elapsed,
                "error": error_msg
            }
            self.results["errors"].append(error_msg)
    
    async def test_orchestration(self):
        """Test orchestration system"""
        print("\n4. Testing Orchestration System...")
        test_name = "orchestration"
        start_time = time.perf_counter()
        
        try:
            from orchestrator_enhanced import orchestrate_security_analysis
            
            # Test orchestration with simple prompt
            result = await orchestrate_security_analysis(
                prompt="What is cybersecurity?",
                context={},
                strategy="adaptive"
            )
            
            print(f"   ✅ Orchestration - Decision: {result.get('final_decision', 'unknown')}")
            print(f"   ✅ Processing Time: {result.get('processing_time', 0):.3f}s")
            
            elapsed = time.perf_counter() - start_time
            self.results["component_tests"][test_name] = {
                "status": "PASS",
                "duration": elapsed,
                "details": f"Orchestration successful - {result.get('strategy_used', 'unknown')} strategy"
            }
            
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            error_msg = f"Orchestration error: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.results["component_tests"][test_name] = {
                "status": "FAIL",
                "duration": elapsed,
                "error": error_msg
            }
            self.results["errors"].append(error_msg)
    
    async def test_api_components(self):
        """Test API components"""
        print("\n5. Testing API Components...")
        test_name = "api_components"
        start_time = time.perf_counter()
        
        try:
            # Test FastAPI imports
            from api.main import app, fast_engine
            print("   ✅ FastAPI application imported")
            
            # Test performance engine
            if hasattr(fast_engine, 'analyze_optimized'):
                print("   ✅ Performance engine methods available")
            
            elapsed = time.perf_counter() - start_time
            self.results["component_tests"][test_name] = {
                "status": "PASS",
                "duration": elapsed,
                "details": "API components available"
            }
            
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            error_msg = f"API component error: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.results["component_tests"][test_name] = {
                "status": "FAIL",
                "duration": elapsed,
                "error": error_msg
            }
            self.results["errors"].append(error_msg)
    
    async def test_integrations(self):
        """Test system integrations"""
        print("\n6. Testing System Integrations...")
        test_name = "integrations"
        start_time = time.perf_counter()
        
        try:
            # Test Streamlit app imports
            import streamlit as st
            print("   ✅ Streamlit available")
            
            # Test app_updated.py imports
            with open('app_updated.py', 'r') as f:
                app_content = f.read()
                if 'orchestrate_security_analysis' in app_content:
                    print("   ✅ Enhanced orchestration integrated in UI")
                
            elapsed = time.perf_counter() - start_time
            self.results["component_tests"][test_name] = {
                "status": "PASS",
                "duration": elapsed,
                "details": "System integrations verified"
            }
            
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            error_msg = f"Integration error: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.results["component_tests"][test_name] = {
                "status": "FAIL",
                "duration": elapsed,
                "error": error_msg
            }
            self.results["errors"].append(error_msg)
    
    def generate_final_report(self):
        """Generate final health check report"""
        print("\n" + "=" * 60)
        print("📊 SYSTEM HEALTH REPORT")
        print("=" * 60)
        
        # Calculate overall status
        total_tests = len(self.results["component_tests"])
        passed_tests = sum(1 for test in self.results["component_tests"].values() if test["status"] == "PASS")
        
        if passed_tests == total_tests:
            self.results["overall_status"] = "HEALTHY"
            status_emoji = "✅"
        elif passed_tests > total_tests * 0.7:
            self.results["overall_status"] = "DEGRADED"
            status_emoji = "⚠️"
        else:
            self.results["overall_status"] = "CRITICAL"
            status_emoji = "❌"
        
        print(f"\n{status_emoji} Overall Status: {self.results['overall_status']}")
        print(f"📈 Tests Passed: {passed_tests}/{total_tests}")
        
        # Component details
        print(f"\n📋 Component Test Results:")
        for test_name, result in self.results["component_tests"].items():
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"   {status_icon} {test_name}: {result['status']} ({result['duration']:.3f}s)")
        
        # Performance metrics
        total_time = sum(test["duration"] for test in self.results["component_tests"].values())
        self.results["performance_metrics"]["total_test_time"] = total_time
        print(f"\n⏱️ Total Test Time: {total_time:.3f}s")
        
        # Errors and warnings
        if self.results["errors"]:
            print(f"\n🚨 Errors Found ({len(self.results['errors'])}):")
            for error in self.results["errors"]:
                print(f"   • {error}")
        
        # Save report
        with open('system_health_report.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Report saved to: system_health_report.json")

async def main():
    """Main health check execution"""
    checker = SystemHealthChecker()
    try:
        await checker.run_comprehensive_check()
    except Exception as e:
        print(f"\n💥 Critical error during health check: {e}")
        traceback.print_exc()
        return 1
    
    return 0 if checker.results["overall_status"] == "HEALTHY" else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
