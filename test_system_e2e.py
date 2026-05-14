#!/usr/bin/env python
"""
End-to-end system test: Sign up → Login → Upload document → Query
"""

import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8001"
TEST_USER = {
    "email": "testuser@example.com",
    "username": "testuser_e2e",
    "password": "TestPass123!",
    "full_name": "Test User E2E",
    "role": "student"
}

def test_health():
    """Check system is ready"""
    print("\n📋 Testing system health...")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            print(f"✅ Backend healthy: {resp.json()}")
            return True
    except Exception as e:
        print(f"❌ Backend not ready: {e}")
        return False

def test_signup():
    """Create a test user"""
    print("\n👤 Signing up test user...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json=TEST_USER,
            timeout=10
        )
        if resp.status_code in [200, 201]:
            print(f"✅ Signup successful")
            return resp.json()
        else:
            print(f"⚠️  Status: {resp.status_code}, Response: {resp.text}")
            return resp.json() if resp.text else None
    except Exception as e:
        print(f"❌ Signup failed: {e}")
        return None

def test_login():
    """Log in and get token"""
    print("\n🔑 Logging in...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            print(f"✅ Login successful, token: {token[:20]}...")
            return token
        else:
            print(f"❌ Login failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def test_upload_document(token):
    """Upload a test document"""
    print("\n📄 Uploading test document...")
    
    # Create a test document
    doc_path = Path("test_document.txt")
    doc_content = """# Computer Network Topologies

## Star Topology

In a star topology, each device has a dedicated point-to-point link only to a central controller, usually called a hub or a switch.

### Advantages of Star Topology:
- Less expensive than mesh: Each device needs only one link and one I/O port to connect it to any number of others.
- Easy to install and reconfigure: Adding or removing devices involves only one connection between that device and the hub.
- Robustness: If one link fails, only that link is affected. All other links remain active.
- Easy fault identification: As long as the hub is working, it can be used to monitor link status and locate faults.

### Disadvantages of Star Topology:
- Single point of failure: If the central hub goes down, the entire network is dead.
- Dependency: The performance of the network depends heavily on the central hub.

## Mesh Topology

In a mesh topology, every device is connected to every other device in the network through a dedicated point-to-point link.

### Advantages:
- No traffic problems due to dedicated links
- Robustness: If one link fails, alternative paths exist
- Security and Privacy: Data is sent along a dedicated line

### Disadvantages:
- High amount of cabling required
- Expensive hardware costs
- Difficult installation and configuration
"""
    
    doc_path.write_text(doc_content)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        with open(doc_path, "rb") as f:
            files = {"file": f}
            resp = requests.post(
                f"{BASE_URL}/api/documents/upload",
                headers=headers,
                files=files,
                timeout=30
            )
        
        if resp.status_code in [200, 201]:
            print(f"✅ Document uploaded successfully")
            data = resp.json()
            print(f"   Document ID: {data.get('id')}")
            print(f"   File path: {data.get('file_path')}")
            doc_path.unlink()  # Clean up
            return data
        else:
            print(f"❌ Upload failed: {resp.status_code} - {resp.text}")
            doc_path.unlink()  # Clean up
            return None
    except Exception as e:
        print(f"❌ Upload error: {e}")
        if doc_path.exists():
            doc_path.unlink()
        return None

def test_chat_query(token):
    """Send a chat query"""
    print("\n💬 Sending query to RAG system...")
    
    query = "What are the advantages and disadvantages of star topology?"
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
                f"{BASE_URL}/api/chat/message",
            json={
                "question": query,
                "topic": "Network Topologies"
            },
            headers=headers,
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer", "")
            confidence = data.get("confidence", 0)
            citations = data.get("citations", [])
            
            print(f"\n✅ Query successful!")
            print(f"\n📝 Question: {query}")
            print(f"\n🤖 Answer: {answer[:300]}...")
            print(f"\n📊 Confidence: {confidence:.2%}")
            print(f"\n📚 Citations: {len(citations)} sources")
            if citations:
                for i, cite in enumerate(citations[:2], 1):
                    print(f"   {i}. {cite}")
            return data
        else:
            print(f"❌ Query failed: {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Query error: {e}")
        return None

def main():
    """Run full end-to-end test"""
    print("=" * 70)
    print("🚀 GraphRAG Learning Platform - End-to-End System Test")
    print("=" * 70)
    
    # Step 1: Health check
    if not test_health():
        print("\n❌ System is not ready. Make sure servers are running:")
        print("   npm run dev")
        return
    
    # Wait a moment for everything to be ready
    time.sleep(2)
    
    # Step 2: Sign up
    signup_result = test_signup()
    
    # Step 3: Login
    token = test_login()
    if not token:
        print("\n❌ Failed to get authentication token")
        return
    
    # Step 4: Upload document
    doc_result = test_upload_document(token)
    if not doc_result:
        print("\n⚠️  Document upload failed, but continuing with query...")
    
    # Step 5: Query the system
    time.sleep(2)  # Give document time to be indexed
    query_result = test_chat_query(token)
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ End-to-End Test Complete!")
    print("=" * 70)
    print(f"\n📌 Summary:")
    print(f"  - User: {TEST_USER['email']}")
    print(f"  - Authenticated: {'Yes' if token else 'No'}")
    print(f"  - Document uploaded: {'Yes' if doc_result else 'No'}")
    print(f"  - Query executed: {'Yes' if query_result else 'No'}")
    print(f"\n🌐 Access the UI at: http://localhost:3000")
    print(f"📖 API docs at: http://localhost:8001/docs")
    print("=" * 70)

if __name__ == "__main__":
    main()
