import requests
import json
import sys

try:
    response = requests.get('http://localhost:8000/events/')
    if response.status_code == 200:
        events = response.json()
        print(f"Total Events: {len(events)}")
        print(json.dumps(events, indent=2))
    else:
        print(f"Error: Status {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Connection Failed: {e}")
