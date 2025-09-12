#!/usr/bin/env python3
"""
Test to verify the NCF race condition fix for concurrent sale finalization.

This test verifies that multiple concurrent finalization requests for the same sale
will result in exactly one NCF being allocated and the operation being idempotent.
"""

import requests
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Test configuration
BASE_URL = "http://localhost:5000"
TEST_SALE_ID = None  # Will be set during test
TEST_SESSION = None

def test_concurrent_finalization():
    """Test that concurrent finalization of the same sale is idempotent."""
    
    print("🔧 Testing NCF Race Condition Fix...")
    print("=" * 50)
    
    # Test data for finalization
    finalization_data = {
        "ncf_type": "consumo",
        "payment_method": "efectivo"
    }
    
    # Function to make finalization request
    def finalize_sale_request(request_id):
        try:
            response = requests.post(
                f"{BASE_URL}/api/sales/{TEST_SALE_ID}/finalize",
                json=finalization_data,
                cookies={'session': TEST_SESSION} if TEST_SESSION else None,
                timeout=10
            )
            return {
                'request_id': request_id,
                'status_code': response.status_code,
                'response': response.json() if response.content else None,
                'success': response.status_code == 200
            }
        except Exception as e:
            return {
                'request_id': request_id,
                'status_code': None,
                'response': None,
                'error': str(e),
                'success': False
            }
    
    # Simulate concurrent requests (5 simultaneous finalization attempts)
    num_concurrent_requests = 5
    print(f"📡 Making {num_concurrent_requests} concurrent finalization requests...")
    
    with ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
        # Submit all requests simultaneously
        futures = [
            executor.submit(finalize_sale_request, i+1) 
            for i in range(num_concurrent_requests)
        ]
        
        # Collect results
        results = []
        for future in as_completed(futures):
            results.append(future.result())
    
    # Analyze results
    print("\n📊 Results Analysis:")
    print("-" * 30)
    
    successful_requests = [r for r in results if r['success']]
    failed_requests = [r for r in results if not r['success']]
    
    print(f"✅ Successful requests: {len(successful_requests)}")
    print(f"❌ Failed requests: {len(failed_requests)}")
    
    # Check that all successful requests returned the same NCF
    if successful_requests:
        unique_ncfs = set()
        for result in successful_requests:
            if result['response'] and 'ncf' in result['response']:
                unique_ncfs.add(result['response']['ncf'])
        
        print(f"🔢 Unique NCFs allocated: {len(unique_ncfs)}")
        print(f"📋 NCF(s): {list(unique_ncfs)}")
        
        # The critical test: Should be exactly 1 unique NCF
        if len(unique_ncfs) == 1:
            print("✅ SUCCESS: Race condition fixed! Only one NCF allocated.")
        else:
            print("❌ FAILURE: Multiple NCFs allocated - race condition still exists!")
            
        # Check idempotency
        all_same_response = True
        first_ncf = None
        for result in successful_requests:
            if result['response'] and 'ncf' in result['response']:
                if first_ncf is None:
                    first_ncf = result['response']['ncf']
                elif result['response']['ncf'] != first_ncf:
                    all_same_response = False
                    break
        
        if all_same_response:
            print("✅ SUCCESS: All requests returned the same NCF (idempotent).")
        else:
            print("❌ FAILURE: Requests returned different NCFs (not idempotent).")
    
    # Show detailed results
    print("\n📋 Detailed Results:")
    print("-" * 30)
    for result in results:
        status = "✅" if result['success'] else "❌"
        req_id = result['request_id']
        status_code = result.get('status_code', 'N/A')
        
        if result['success'] and result['response']:
            ncf = result['response'].get('ncf', 'N/A')
            message = result['response'].get('message', '')
            print(f"{status} Request {req_id}: HTTP {status_code} - NCF: {ncf} {message}")
        else:
            error = result.get('error', 'Unknown error')
            print(f"{status} Request {req_id}: HTTP {status_code} - Error: {error}")

if __name__ == "__main__":
    print("📝 Note: This test requires:")
    print("   1. Flask app running on localhost:5000")
    print("   2. A valid sale ID to test with")
    print("   3. Proper authentication session")
    print("\n🚀 To run a live test, update TEST_SALE_ID and TEST_SESSION variables")
    print("   and ensure you have a pending sale in the database.")
    
    # Example usage (commented out for safety):
    # TEST_SALE_ID = 123  # Replace with actual sale ID
    # TEST_SESSION = "your_session_cookie"  # Replace with actual session
    # test_concurrent_finalization()