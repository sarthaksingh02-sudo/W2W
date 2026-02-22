import requests
import time
import json
import os

print("Watching for events...")
last_count = 0

while True:
    try:
        response = requests.get('http://localhost:8000/events/')
        if response.status_code == 200:
            events = response.json()
            if len(events) > last_count:
                new_events = events[last_count:]
                print(f"\n[NEW EVENTS DETECTED] Count: {len(new_events)}")
                for e in new_events:
                    print(f" - {e['type']} by User {e['user_id']} at {e['timestamp']}")
                last_count = len(events)
        else:
            pass
    except:
        pass
    
    time.sleep(2)
