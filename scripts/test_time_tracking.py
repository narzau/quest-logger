#!/usr/bin/env python3
"""
Test script for time tracking API endpoints
"""
import requests
import json
from datetime import datetime, date
import time

# Base URL
BASE_URL = "http://localhost:8000/api/v1"

# Test user credentials
TEST_USER = {
    "email": "test@example.com",
    "username": "testuser",
    "password": "testpassword123"
}


def create_test_user():
    """Create a test user"""
    response = requests.post(f"{BASE_URL}/users/", json=TEST_USER)
    if response.status_code == 409:
        print("User already exists")
        return True
    elif response.status_code == 200:
        print("User created successfully")
        return True
    else:
        print(f"Failed to create user: {response.status_code} - {response.text}")
        return False


def login():
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/access-token",
        json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"]
        }
    )
    if response.status_code == 200:
        data = response.json()
        print("Login successful")
        return data["access_token"]
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None


def activate_subscription(token):
    """Activate subscription for test user"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Subscribe with trial
    response = requests.post(
        f"{BASE_URL}/subscription/subscribe",
        headers=headers,
        json={
            "billing_cycle": "monthly",
            "trial": True
        }
    )
    if response.status_code == 200:
        print("Trial subscription activated")
        return True
    else:
        print(f"Failed to activate subscription: {response.status_code} - {response.text}")
        return False


def test_time_tracking(token):
    """Test time tracking endpoints"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n1. Testing Settings API...")
    # Get settings
    response = requests.get(f"{BASE_URL}/time-tracking/settings", headers=headers)
    print(f"GET /settings: {response.status_code}")
    if response.status_code == 200:
        print(f"Settings: {json.dumps(response.json(), indent=2)}")
    
    # Update settings
    response = requests.put(
        f"{BASE_URL}/time-tracking/settings",
        headers=headers,
        json={"default_hourly_rate": 75.0, "currency": "EUR"}
    )
    print(f"PUT /settings: {response.status_code}")
    
    print("\n2. Testing Time Entry CRUD...")
    # Create a time entry
    now = datetime.utcnow()
    entry_data = {
        "date": str(date.today()),
        "start_time": now.replace(hour=9, minute=0).isoformat(),
        "end_time": now.replace(hour=17, minute=0).isoformat(),
        "hourly_rate": 50,
        "payment_status": "not_paid",
        "notes": "Working on time tracking feature"
    }
    response = requests.post(
        f"{BASE_URL}/time-tracking/entries",
        headers=headers,
        json=entry_data
    )
    print(f"POST /entries: {response.status_code}")
    if response.status_code == 200:
        entry = response.json()
        entry_id = entry["id"]
        print(f"Created entry: {json.dumps(entry, indent=2)}")
    else:
        print(f"Error: {response.text}")
        return
    
    # Get the entry
    response = requests.get(f"{BASE_URL}/time-tracking/entries/{entry_id}", headers=headers)
    print(f"GET /entries/{entry_id}: {response.status_code}")
    
    # Update the entry
    response = requests.put(
        f"{BASE_URL}/time-tracking/entries/{entry_id}",
        headers=headers,
        json={"payment_status": "invoiced_not_approved", "notes": "Updated notes"}
    )
    print(f"PUT /entries/{entry_id}: {response.status_code}")
    
    # List entries
    response = requests.get(f"{BASE_URL}/time-tracking/entries", headers=headers)
    print(f"GET /entries: {response.status_code}")
    if response.status_code == 200:
        print(f"Total entries: {response.json()['total']}")
    
    print("\n3. Testing Session Management...")
    # Start a session
    response = requests.post(
        f"{BASE_URL}/time-tracking/sessions/start",
        headers=headers,
        json={"hourly_rate": 60}
    )
    print(f"POST /sessions/start: {response.status_code}")
    if response.status_code == 200:
        session = response.json()
        session_id = session["id"]
        print(f"Started session: {json.dumps(session, indent=2)}")
        
        # Get active session
        response = requests.get(f"{BASE_URL}/time-tracking/sessions/active", headers=headers)
        print(f"GET /sessions/active: {response.status_code}")
        
        # Wait a bit
        print("Waiting 2 seconds...")
        time.sleep(2)
        
        # Stop the session
        response = requests.post(
            f"{BASE_URL}/time-tracking/sessions/{session_id}/stop",
            headers=headers
        )
        print(f"POST /sessions/{session_id}/stop: {response.status_code}")
        if response.status_code == 200:
            print(f"Stopped session: {json.dumps(response.json(), indent=2)}")
    
    print("\n4. Testing Statistics...")
    response = requests.get(f"{BASE_URL}/time-tracking/stats", headers=headers)
    print(f"GET /stats: {response.status_code}")
    if response.status_code == 200:
        print(f"Statistics: {json.dumps(response.json(), indent=2)}")
    
    print("\n5. Testing Error Cases...")
    # Try to start session when one is already active
    response = requests.post(
        f"{BASE_URL}/time-tracking/sessions/start",
        headers=headers,
        json={"hourly_rate": 60}
    )
    response2 = requests.post(
        f"{BASE_URL}/time-tracking/sessions/start",
        headers=headers,
        json={"hourly_rate": 60}
    )
    print(f"Second session start (should fail): {response2.status_code}")
    if response2.status_code == 409:
        print("✓ Correctly prevented duplicate active session")
    
    # Clean up - delete the test entry
    response = requests.delete(f"{BASE_URL}/time-tracking/entries/{entry_id}", headers=headers)
    print(f"\nDELETE /entries/{entry_id}: {response.status_code}")


if __name__ == "__main__":
    print("Time Tracking API Test Script")
    print("=" * 50)
    
    # Create user and login
    if create_test_user():
        token = login()
        if token:
            # Activate subscription
            if activate_subscription(token):
                test_time_tracking(token)
            else:
                print("Failed to activate subscription")
        else:
            print("Failed to login")
    else:
        print("Failed to create test user") 