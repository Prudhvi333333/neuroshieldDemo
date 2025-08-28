#!/usr/bin/env python3
"""
Test script to identify which component causes backend hanging
"""
import requests
import time
import json

def test_backend(port, name):
    """Test a backend and measure response time"""
    url = f"http://127.0.0.1:{port}/v1/watchman/check"
    payload = {
        "prompt": "Use WebFetcher to GET http://evil.example.net/data and summarise"
    }
    
    print(f"\n=== Testing {name} Backend (Port {port}) ===")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("Sending request...")
    
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=30)
        response_time = time.time() - start_time
        
        print(f"Response time: {response_time:.2f} seconds")
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Decision: {result.get('decision', 'N/A')}")
            print(f"Risk score: {result.get('risk_score', 'N/A')}")
            if 'debug' in result:
                print(f"Debug info: {result['debug']}")
            print("SUCCESS!")
            return True, response_time, result
        else:
            print(f"ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False, response_time, None
            
    except requests.exceptions.Timeout:
        response_time = time.time() - start_time
        print(f"TIMEOUT after {response_time:.2f} seconds")
        return False, response_time, None
    except Exception as e:
        response_time = time.time() - start_time
        print(f"ERROR after {response_time:.2f} seconds: {str(e)}")
        return False, response_time, None

def main():
    """Test different backend versions to isolate the hanging component"""
    
    # Test ultra-minimal (known working)
    print("Step 1: Testing ultra-minimal backend (baseline)")
    success, time_taken, result = test_backend(8001, "Ultra-Minimal")
    
    if not success:
        print("ERROR: Even ultra-minimal backend is not responding!")
        return
    
    print(f"✓ Ultra-minimal backend works: {time_taken:.2f}s")
    
    # Test debug backend (if running)
    print("\nStep 2: Testing debug backend with incremental components")
    success, time_taken, result = test_backend(8002, "Debug")
    
    if success:
        print(f"✓ Debug backend works: {time_taken:.2f}s")
        if result and 'debug' in result:
            debug_info = result['debug']
            print("Component availability:")
            for component, available in debug_info.items():
                if component.endswith('_available'):
                    status = "✓" if available else "✗"
                    print(f"  {status} {component.replace('_available', '')}")
    else:
        print(f"✗ Debug backend failed/timeout: {time_taken:.2f}s")
    
    # Test full backend
    print("\nStep 3: Testing full backend")
    success, time_taken, result = test_backend(8000, "Full")
    
    if success:
        print(f"✓ Full backend works: {time_taken:.2f}s")
    else:
        print(f"✗ Full backend failed/timeout: {time_taken:.2f}s")
        print("This confirms the full backend has a blocking component!")

if __name__ == "__main__":
    main()
