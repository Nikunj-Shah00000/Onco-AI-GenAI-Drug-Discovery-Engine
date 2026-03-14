#!/usr/bin/env python3
"""
Integration tests for OncoAI
"""
import requests
import json
import time
import sys

API_ENDPOINT = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:3000'

def test_health():
    """Test API health"""
    response = requests.get(f"{API_ENDPOINT}/health")
    assert response.status_code == 200
    print("✅ Health check passed")

def test_create_campaign():
    """Test creating a new campaign"""
    payload = {
        "protein_target": "EGFR",
        "name": "Test Campaign",
        "num_molecules": 100
    }
    
    response = requests.post(f"{API_ENDPOINT}/campaign", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert 'campaign_id' in data
    assert data['status'] == 'INITIATED'
    
    print(f"✅ Campaign created: {data['campaign_id']}")
    return data['campaign_id']

def test_get_campaign(campaign_id):
    """Test getting campaign status"""
    response = requests.get(f"{API_ENDPOINT}/campaign/{campaign_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert 'campaign' in data
    assert data['campaign']['campaignId'] == campaign_id
    
    print(f"✅ Campaign retrieved: {data['campaign']['status']}")
    return data

def test_wait_for_completion(campaign_id, timeout=300):
    """Wait for campaign to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        data = test_get_campaign(campaign_id)
        status = data['campaign']['status']
        
        if status == 'COMPLETED':
            print(f"✅ Campaign completed in {time.time() - start_time:.1f}s")
            return data.get('results')
        elif status == 'FAILED':
            print("❌ Campaign failed")
            return None
            
        print(f"Status: {status} - Waiting...")
        time.sleep(5)
        
    print("❌ Timeout waiting for completion")
    return None

def test_results(results):
    """Test results format"""
    assert results is not None
    assert 'candidates' in results
    
    candidates = results['candidates']
    assert len(candidates) > 0
    
    first = candidates[0]
    assert 'smiles' in first
    assert 'binding_score' in first
    assert 'docking_score' in first
    
    print(f"✅ Found {len(candidates)} candidates")
    print(f"Top candidate: {first['smiles']} (Score: {first['binding_score']:.3f})")

def main():
    print(f"Testing OncoAI at {API_ENDPOINT}")
    print("=" * 50)
    
    try:
        test_health()
        campaign_id = test_create_campaign()
        results = test_wait_for_completion(campaign_id)
        test_results(results)
        
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()