#!/usr/bin/env python3
"""
Comprehensive test runner for NeuroShield API and modules
Executes all tests and generates detailed reports
"""

import subprocess
import sys
import time
import json
from pathlib import Path
import threading
import requests
from typing import Dict, Any

def start_api_server():
    """Start FastAPI server in background for testing"""
    try:
        # Start API server
        process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "api.main:app", 
            "--host", "0.0.0.0", "--port", "8000"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    print("API server started successfully")
                    return process
            except:
                time.sleep(1)
        
        print("Failed to start API server")
        process.terminate()
        return None
        
    except Exception as e:
        print(f"Error starting API server: {e}")
        return None

def run_pytest_tests():
    """Run pytest test suite"""
    print("\nRunning pytest test suite...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/test_api_endpoints.py", 
            "-v", "--tb=short"
        ], capture_output=True, text=True, timeout=120)
        
        print("PYTEST OUTPUT:")
        print(result.stdout)
        if result.stderr:
            print("PYTEST ERRORS:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Pytest tests timed out")
        return False
    except Exception as e:
        print(f"❌ Error running pytest: {e}")
        return False

def run_custom_tests():
    """Run custom prompt/response validation tests"""
    print("\n📝 Running custom prompt/response tests...")
    
    try:
        result = subprocess.run([
            sys.executable, "tests/test_prompts_responses.py"
        ], capture_output=True, text=True, timeout=180)
        
        print("CUSTOM TESTS OUTPUT:")
        print(result.stdout)
        if result.stderr:
            print("CUSTOM TESTS ERRORS:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Custom tests timed out")
        return False
    except Exception as e:
        print(f"❌ Error running custom tests: {e}")
        return False

def validate_core_modules():
    """Validate core NeuroShield modules can be imported and initialized"""
    print("\nValidating core modules...")
    
    try:
        # Add current directory to Python path
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        # Test imports
        from langgraph_core.firewall_graph import build_firewall_graph
        from agents.initial_analysis_agent import InitialAnalysisAgent
        from agents.response_verifier_agent import ResponseVerifierAgent
        from api.main import app
        from api.client import NeuroShieldAPIClient
        
        print("Core modules imported successfully")
        return True
        
    except ImportError as e:
        print(f"Core module validation failed: {e}")
        return False

def generate_test_report(pytest_success: bool, custom_success: bool, modules_success: bool):
    """Generate comprehensive test report"""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "test_results": {
            "pytest_api_tests": pytest_success,
            "custom_prompt_tests": custom_success,
            "core_modules_validation": modules_success
        },
        "overall_success": pytest_success and custom_success and modules_success,
        "summary": {
            "total_test_categories": 3,
            "passed_categories": sum([pytest_success, custom_success, modules_success]),
            "failed_categories": 3 - sum([pytest_success, custom_success, modules_success])
        }
    }
    
    # Save report
    results_dir = Path("tests/results")
    results_dir.mkdir(exist_ok=True)
    
    with open(results_dir / "comprehensive_test_report.json", 'w') as f:
        json.dump(report, f, indent=2)
    
    return report

def main():
    """Main test execution function"""
    print("🛡️ NeuroShield Comprehensive Test Suite")
    print("=" * 50)
    
    # Step 1: Validate core modules
    modules_success = validate_core_modules()
    
    # Step 2: Start API server
    api_process = start_api_server()
    
    try:
        # Step 3: Run pytest tests
        pytest_success = False
        if api_process:
            pytest_success = run_pytest_tests()
        else:
            print("⚠️ Skipping API tests - server failed to start")
        
        # Step 4: Run custom tests
        custom_success = run_custom_tests()
        
        # Step 5: Generate report
        report = generate_test_report(pytest_success, custom_success, modules_success)
        
        # Step 6: Display summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        print(f"Core Modules: {'✅ PASS' if modules_success else '❌ FAIL'}")
        print(f"API Tests: {'✅ PASS' if pytest_success else '❌ FAIL'}")
        print(f"Custom Tests: {'✅ PASS' if custom_success else '❌ FAIL'}")
        print(f"Overall: {'✅ ALL TESTS PASSED' if report['overall_success'] else '❌ SOME TESTS FAILED'}")
        
        if report['overall_success']:
            print("\n🎉 NeuroShield is ready for production!")
        else:
            print("\n⚠️ Please review failed tests and fix issues before deployment")
        
        return report['overall_success']
        
    finally:
        # Cleanup: Stop API server
        if api_process:
            api_process.terminate()
            api_process.wait()
            print("\n🛑 API server stopped")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
