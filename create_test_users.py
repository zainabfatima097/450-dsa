import requests
import random

# Base URL of your app
BASE_URL = "http://localhost:5000"

def create_user(email, password, name):
    session = requests.Session()
    
    # Register
    register_data = {
        'name': name,
        'email': email,
        'password': password
    }
    resp = session.post(f"{BASE_URL}/register", data=register_data)
    
    if resp.status_code == 200 or "already registered" not in resp.text:
        print(f"✅ Created: {email}")
        
        # Login
        login_data = {
            'email': email,
            'password': password
        }
        session.post(f"{BASE_URL}/login", data=login_data)
        
        # Mark some random questions as done
        # First get a topic
        topics_resp = session.get(f"{BASE_URL}/")
        # This is simplified - you may need to extract topic IDs
        print(f"   Logged in as {name}")
        
        return True
    return False

# Create 20 test users
for i in range(1, 21):
    email = f"testuser{i}@example.com"
    name = f"Test User {i}"
    password = "password123"
    create_user(email, password, name)

print("\n🎉 Created 20 test users!")
print("Login with any: testuser1@example.com / password123")