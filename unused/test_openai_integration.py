#!/usr/bin/env python3
"""
Test OpenAI integration for NeuroShield
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_openai_integration():
    """Test that OpenAI integration is working"""
    
    print("🔧 Testing OpenAI Integration")
    print("=" * 30)
    
    # Test 1: Import and basic setup
    try:
        from llm_utils import call_llm, call_llm_json, call_llm_with_json_response
        print("✅ OpenAI imports successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test 2: Simple text call
    try:
        response = call_llm("What is cybersecurity?")
        print(f"✅ Text call successful: {response[:50]}...")
    except Exception as e:
        print(f"❌ Text call failed: {e}")
    
    # Test 3: JSON call
    try:
        json_response = call_llm_json('Respond in JSON format: {"test": "success"}')
        print(f"✅ JSON call successful: {json_response[:50]}...")
    except Exception as e:
        print(f"❌ JSON call failed: {e}")
    
    # Test 4: Parsed JSON response
    try:
        parsed = call_llm_with_json_response('Return JSON with classification: Safe, risk_score: 0.1')
        print(f"✅ Parsed JSON successful: {parsed}")
    except Exception as e:
        print(f"❌ Parsed JSON failed: {e}")
    
    print(f"\n🎯 OpenAI integration test complete")

if __name__ == "__main__":
    test_openai_integration()
