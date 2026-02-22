import requests
import time

print("Waiting for backend...")
for i in range(10):
    try:
        r = requests.get('http://localhost:8000/docs')
        if r.status_code == 200:
            print("Backend is up!")
            break
    except:
        pass
    time.sleep(1)

print("Checking /zones/ endpoint...")
try:
    r = requests.get('http://localhost:8000/zones/', params={'camera_id': 1})
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"Failed: {e}")
