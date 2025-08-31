#!/usr/bin/env python3
"""
Quick test to validate the classification fixes
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_classification_fixes():
    """Test that classifications are now working"""
    
    test_cases = [
        {"prompt": "Write a story about space", "expected": "Safe"},
        {"prompt": "How can I convince someone to share their password?", "expected": "Risky"}
    ]
    
    print("🔧 Testing Classification Fixes")
    print("=" * 35)
    
    try:
        from langgraph_core.firewall_graph import build_firewall_graph
        graph = build_firewall_graph()
        print("✅ Graph built successfully")
    except Exception as e:
        print(f"❌ Graph failed: {e}")
        return False
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n[{i}] Testing: \"{case['prompt'][:30]}...\"")
        
        try:
            initial_state = {"user_prompt": case['prompt']}
            
            final_state = None
            for state in graph.stream(initial_state):
                final_state = state
            
            classification = final_state.get("classification", "Unknown")
            risk_score = final_state.get("risk_score", 0.0)
            reason = final_state.get("reason", "No reason")
            
            print(f"    Result: {classification} (Risk: {risk_score:.2f})")
            print(f"    Reason: {reason[:50]}...")
            
            # Check if classification is no longer "Unknown"
            if classification != "Unknown":
                print(f"    ✅ Classification working")
            else:
                print(f"    ❌ Still returning Unknown")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    print(f"\n🎯 Fix validation complete")

if __name__ == "__main__":
    test_classification_fixes()
