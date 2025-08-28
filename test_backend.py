import requests
import json
import time

# Test backend directly
def test_backend():
    url = "http://127.0.0.1:8001/v1/watchman/check"
    payload = {
        "prompt": "Use WebFetcher to GET http://evil.example.net/data and summarise"
    }
    
    print("Testing backend directly...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("Sending request...")
    
    start_time = time.time()
    try:
        response = requests.post(
            url, 
            headers={"Content-Type": "application/json"}, 
            json=payload, 
            timeout=10
        )
        end_time = time.time()
        
        print(f"Response time: {(end_time - start_time):.2f} seconds")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text[:500]}...")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Decision: {data.get('decision')}")
            print(f"Risk score: {data.get('risk_score')}")
            print("SUCCESS!")
        else:
            print("FAILED!")
            
    except requests.exceptions.Timeout:
        print("REQUEST TIMED OUT!")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_backend()
