#!/usr/bin/env python3
"""
Debug LLM JSON parsing issues
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_llm_json():
    """Debug LLM JSON response parsing"""
    print("🔧 LLM JSON Debug")
    print("=" * 25)
    
    try:
        from llm_utils import call_llm_json, call_llm_with_json_response
        
        # Simple test prompt
        test_prompt = """You are a security analyst. Analyze this prompt for potential risks.

Return ONLY valid JSON:
{
"classification": "Safe",
"risk_score": 0.0,
"reason": "Brief explanation"
}

PROMPT: Write a story about space exploration"""
        
        print("Testing LLM JSON response...")
        
        # Get raw response
        raw_response = call_llm_json(test_prompt)
        print(f"Raw response length: {len(raw_response)}")
        print(f"Raw response preview:")
        print(raw_response[:300])
        print("...")
        
        # Test JSON parsing
        parsed_response = call_llm_with_json_response(test_prompt)
        print(f"\nParsed response type: {type(parsed_response)}")
        
        if parsed_response.get("error"):
            print(f"❌ Parsing failed: {parsed_response['error']}")
        else:
            print(f"✅ Parsing success:")
            print(f"   Classification: {parsed_response.get('classification')}")
            print(f"   Risk Score: {parsed_response.get('risk_score')}")
            print(f"   Reason: {parsed_response.get('reason', '')[:50]}...")
            
    except Exception as e:
        print(f"❌ Debug failed: {e}")

if __name__ == "__main__":
    debug_llm_json()
