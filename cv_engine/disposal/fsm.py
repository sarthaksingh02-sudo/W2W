import cv2
import time
import os
import math
import numpy as np
import requests
import json
import threading
from enum import Enum, auto
from shapely.geometry import Point, Polygon

# Import Models
from backend.app.models.models import EventType

# API Config
API_URL = "http://localhost:8000"

class DisposalState(Enum):
    IDLE = auto()          # New object detected
    POSSESSION = auto()    # Near a person
    SEPARATION = auto()    # Moving away from person
    MOVING = auto()        # Object in motion (in flight)
    STATIONARY = auto()    # Stopped moving
    CONFIRMED = auto()     # Event logged

class DisposalFSM:
    def __init__(self, camera_id=1, bin_polygons=None):
        self.camera_id = camera_id
        self.waste_states = {} # track_id -> state_data
        self.bin_zones = [] # [(label, type, Polygon)]
        self.frame_counter = 0
        
        if bin_polygons:
            self._parse_zones(bin_polygons)
            
        # Constants from Requirements
        self.POSSESSION_DIST = 100
        self.POSSESSION_TIME = 0.5
        self.SEPARATION_DIST = 150
        self.STATIONARY_VEL = 2.0
        self.STATIONARY_TIME = 1.0

    def _parse_zones(self, zones_data):
        self.bin_zones = []
        for z in zones_data:
            if isinstance(z, Polygon):
                self.bin_zones.append(('Bin', 'general', z))
            elif isinstance(z, dict):
                coords = json.loads(z['coordinates']) if isinstance(z['coordinates'], str) else z['coordinates']
                self.bin_zones.append((z['label'], z.get('zone_type', 'general'), Polygon(coords)))
            elif isinstance(z, list):
                self.bin_zones.append(('Bin', 'general', Polygon(z)))

    def update(self, person_tracks, waste_tracks, frame_shape, frame=None, face_system=None):
        self.frame_counter += 1
        active_waste_ids = set()

        for t in waste_tracks:
            track_id = t['track_id']
            box = t['bbox']
            obj_type = t.get('class', 'object')
            active_waste_ids.add(track_id)
            center = ((box[0]+box[2])/2, (box[1]+box[3])/2)
            now = time.time()
            
            if track_id not in self.waste_states:
                self.waste_states[track_id] = {
                    'state': DisposalState.IDLE,
                    'owner': None,
                    'history': [], 
                    'ts_start': now,
                    'state_entered': now,
                    'proximity_start': None,
                    'obj_type': obj_type
                }

            state_data = self.waste_states[track_id]
            curr_state = state_data['state']
            state_data['history'].append(center)
            if len(state_data['history']) > 30: state_data['history'].pop(0)

            # Velocity calculation (avg over last 3 frames)
            velocity = 0
            if len(state_data['history']) > 2:
                p1 = state_data['history'][-2]
                p2 = state_data['history'][-1]
                velocity = math.hypot(p2[0]-p1[0], p2[1]-p1[1])

            # === STATE MACHINE ===
            
            # 1. IDLE -> POSSESSION
            if curr_state == DisposalState.IDLE:
                closest_p = None
                min_dist = float('inf')
                for p in person_tracks:
                    p_box = p['bbox']
                    p_center = ((p_box[0]+p_box[2])/2, (p_box[1]+p_box[3])/2)
                    dist = math.hypot(center[0]-p_center[0], center[1]-p_center[1])
                    if dist < min_dist:
                        min_dist = dist
                        closest_p = p['track_id']
                
                if min_dist < self.POSSESSION_DIST:
                    if state_data['proximity_start'] is None:
                        state_data['proximity_start'] = now
                    elif now - state_data['proximity_start'] >= self.POSSESSION_TIME:
                        state_data['state'] = DisposalState.POSSESSION
                        state_data['owner'] = closest_p
                        state_data['state_entered'] = now
                        print(f"[FSM] #{track_id} -> POSSESSION by Person #{closest_p}")
                else:
                    state_data['proximity_start'] = None

            # 2. POSSESSION -> SEPARATION
            elif curr_state == DisposalState.POSSESSION:
                owner_track = next((p for p in person_tracks if p['track_id'] == state_data['owner']), None)
                if owner_track:
                    p_box = owner_track['bbox']
                    p_center = ((p_box[0]+p_box[2])/2, (p_box[1]+p_box[3])/2)
                    dist = math.hypot(center[0]-p_center[0], center[1]-p_center[1])
                    if dist > self.SEPARATION_DIST:
                        state_data['state'] = DisposalState.SEPARATION
                        state_data['state_entered'] = now
                        print(f"[FSM] #{track_id} -> SEPARATION from Person #{state_data['owner']}")
                else:
                    # Person left frame
                    state_data['state'] = DisposalState.SEPARATION
                    state_data['state_entered'] = now
                    print(f"[FSM] #{track_id} -> SEPARATION (Owner left frame)")

            # 3. SEPARATION -> MOVING
            elif curr_state == DisposalState.SEPARATION:
                # Immediate transition to moving if velocity is high, or wait for stationary
                if velocity >= self.STATIONARY_VEL:
                    state_data['state'] = DisposalState.MOVING
                    state_data['state_entered'] = now
                elif now - state_data['state_entered'] > 0.5: # Small buffer
                    state_data['state'] = DisposalState.STATIONARY
                    state_data['state_entered'] = now

            # 4. MOVING -> STATIONARY
            elif curr_state == DisposalState.MOVING:
                if velocity < self.STATIONARY_VEL:
                    state_data['state'] = DisposalState.STATIONARY
                    state_data['state_entered'] = now
                    print(f"[FSM] #{track_id} -> STATIONARY")

            # 5. STATIONARY -> CONFIRMED
            elif curr_state == DisposalState.STATIONARY:
                if velocity >= self.STATIONARY_VEL:
                    state_data['state'] = DisposalState.MOVING
                    state_data['state_entered'] = now
                elif now - state_data['state_entered'] >= self.STATIONARY_TIME:
                    z_label, z_type = self._check_zones(center)
                    event_type = EventType.PROPER_DISPOSAL if z_label else EventType.VIOLATION
                    
                    print(f"[FSM] #{track_id} -> CONFIRMED ({event_type.value})")
                    
                    now_ts = int(now)
                    fname = f"event_{now_ts}_{track_id}.jpg"
                    if frame is not None:
                        self._capture_evidence(frame, box, fname)
                    
                    self._save_event(event_type, state_data, track_id, face_system, fname)
                    state_data['state'] = DisposalState.CONFIRMED

        # Cleanup lost tracks
        for tid in list(self.waste_states.keys()):
            if tid not in active_waste_ids and self.waste_states[tid]['state'] != DisposalState.CONFIRMED:
                # If a track is lost before confirmation, we could potentially log it as "Discarded" or just ignore
                pass

    def _check_zones(self, point_tuple):
        pt = Point(point_tuple)
        for label, z_type, poly in self.bin_zones:
            if poly.contains(pt):
                return label, z_type
        return None, None

    def _capture_evidence(self, frame, box, filename):
        try:
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = map(int, box)
            pad = 150
            crop = frame[max(0, y1-pad):min(h, y2+pad), max(0, x1-pad):min(w, x2+pad)]
            
            # Use absolute path to ensure it works from any CWD
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app", "static", "images"))
            os.makedirs(base_dir, exist_ok=True)
            save_path = os.path.join(base_dir, filename)
            
            cv2.imwrite(save_path, crop)
            print(f"[FSM] Evidence captured: {filename}")
        except Exception as e:
            print(f"[FSM] Evidence capture failed: {e}")

    def _save_event(self, event_type, state_data, waste_id, face_sys, image_name):
        user_id = face_sys.get_user_id(state_data['owner']) if face_sys and state_data['owner'] else None
        
        payload = {
            "event_type": event_type.value,
            "confidence": 0.98,
            "camera_id": self.camera_id,
            "user_id": user_id,
            "image_path": image_name,
            "telemetry": {
                "object_type": state_data['obj_type'],
                "trajectory": state_data['history'],
                "track_id": waste_id
            }
        }
        
        def _post():
            try:
                requests.post(f"{API_URL}/events/", json=payload, timeout=3)
            except: pass

        threading.Thread(target=_post, daemon=True).start()
