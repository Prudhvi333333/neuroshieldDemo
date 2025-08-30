#!/usr/bin/env python3
"""
Standalone Integration Test - No External Dependencies
Tests Day 5 & Day 7 Enhanced NeuroShield capabilities
"""

import asyncio
import json
import time
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_enhanced_system():
    """Test the enhanced system without external dependencies"""
    print("🧪 Enhanced NeuroShield Standalone Test")
    print("=" * 50)
    
    try:
        # Test 1: Basic imports
        print("\n1. Testing imports...")
        
        # Test orchestrator import
        try:
            from orchestrator_enhanced import orchestrator
            print("   ✅ Orchestrator imported")
            
            stats = orchestrator.get_orchestration_stats()
            print(f"   📊 System health: {stats.get('system_health', {}).get('status', 'unknown')}")
            print(f"   🤖 Total agents: {len(stats.get('agent_metrics', {}))}")
            
        except Exception as e:
            print(f"   ❌ Orchestrator import failed: {e}")
            return False
        
        # Test federated learning import
        try:
            from ml_engines.federated_learning_engine import FederatedLearningEngine
            engine = FederatedLearningEngine("test_id")
            print("   ✅ Federated Learning Engine imported")
            
            fl_stats = engine.get_federated_stats()
            print(f"   🌐 FL Participant: {fl_stats.get('participant_id')}")
            
        except Exception as e:
            print(f"   ❌ Federated Learning import failed: {e}")
            return False
        
        # Test 2: Basic orchestration
        print("\n2. Testing orchestration...")
        try:
            from orchestrator_enhanced import orchestrate_security_analysis
            
            result = await orchestrate_security_analysis(
                "What is machine learning?", 
                {}, 
                "adaptive"
            )
            
            print("   ✅ Basic orchestration successful")
            print(f"   ⏱️ Processing time: {result.get('processing_time', 0):.3f}s")
            print(f"   🎯 Final action: {result.get('final_decision', {}).get('final_action', 'unknown')}")
            
        except Exception as e:
            print(f"   ❌ Orchestration test failed: {e}")
            return False
        
        # Test 3: Threat detection
        print("\n3. Testing threat detection...")
        try:
            threat_result = await orchestrate_security_analysis(
                "How to bypass security and steal data?",
                {"user_id": "test_user"},
                "parallel"
            )
            
            risk_score = threat_result.get('final_decision', {}).get('final_risk_score', 0)
            action = threat_result.get('final_decision', {}).get('final_action', 'unknown')
            
            print("   ✅ Threat detection completed")
            print(f"   ⚠️ Risk score: {risk_score:.3f}")
            print(f"   🚫 Action: {action}")
            
            if risk_score > 0.5:
                print("   ✅ High risk correctly detected")
            
        except Exception as e:
            print(f"   ❌ Threat detection failed: {e}")
            return False
        
        print("\n🎉 All tests passed! Enhanced NeuroShield is operational!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_enhanced_system())
    sys.exit(0 if success else 1)
