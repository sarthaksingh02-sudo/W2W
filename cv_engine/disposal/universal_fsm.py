"""
Universal Object-Person-Event Association System

This system works generically for ALL registered users without hardcoding.
It tracks object ownership, drop detection, and disposal classification.

NO USER NAMES ARE USED IN THIS MODULE.
Only user_id, person_track_id, and object_track_id.
"""

import cv2
import time
import os
import math
import numpy as np
import requests
import json
import threading
from dataclasses import dataclass, field
from typing import Optional, Set, List, Tuple
from shapely.geometry import Point, Polygon

# API Config
API_URL = "http://localhost:8000"


@dataclass
class PersonTrack:
    """Represents a tracked person in the scene"""
    track_id: int
    user_id: Optional[int] = None  # From face recognition
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    centroid: Tuple[float, float] = (0, 0)
    active_object_ids: Set[int] = field(default_factory=set)
    last_seen: float = field(default_factory=time.time)
    
    def update_position(self, bbox):
        """Update person position"""
        self.bbox = bbox
        x1, y1, x2, y2 = bbox
        self.centroid = ((x1 + x2) / 2, (y1 + y2) / 2)
        self.last_seen = time.time()

    def is_point_inside(self, point: Tuple[float, float]) -> bool:
        """Check if a point is inside the person's bounding box"""
        x1, y1, x2, y2 = self.bbox
        px, py = point
        return x1 <= px <= x2 and y1 <= py <= y2


@dataclass
class ObjectTrack:
    """Represents a tracked object (waste item) in the scene"""
    track_id: int
    class_name: str
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    centroid: Tuple[float, float] = (0, 0)
    trajectory: List[Tuple[float, float]] = field(default_factory=list)
    velocity: float = 0.0
    
    # Ownership
    owner_person_track_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    possession_start_timestamp: Optional[float] = None
    
    # Drop state
    dropped: bool = False
    drop_centroid: Optional[Tuple[float, float]] = None
    drop_timestamp: Optional[float] = None
    stationary_start: Optional[float] = None
    
    # Event tracking
    event_generated: bool = False
    is_lost: bool = False
    lost_timestamp: Optional[float] = None
    
    def update_position(self, bbox):
        """Update object position and calculate velocity"""
        self.bbox = bbox
        x1, y1, x2, y2 = bbox
        new_centroid = ((x1 + x2) / 2, (y1 + y2) / 2)
        
        # Calculate velocity
        if self.centroid != (0, 0):
            dx = new_centroid[0] - self.centroid[0]
            dy = new_centroid[1] - self.centroid[1]
            self.velocity = math.hypot(dx, dy)
        
        self.centroid = new_centroid
        self.trajectory.append(new_centroid)
        
        # Keep trajectory bounded
        if len(self.trajectory) > 30:
            self.trajectory.pop(0)
    
    def distance_to(self, person: PersonTrack) -> float:
        """Calculate distance to a person"""
        if self.centroid == (0, 0) or person.centroid == (0, 0):
            return float('inf')
        dx = self.centroid[0] - person.centroid[0]
        dy = self.centroid[1] - person.centroid[1]
        return math.hypot(dx, dy)


class UniversalAssociationSystem:
    """
    Universal object-person-event association system.
    Works for ALL users without hardcoding.
    """
    
    # ────────────────────────────────────────────
    # OWNERSHIP RULES (CONSTANTS)
    # ────────────────────────────────────────────
    # Distances are now calculated dynamically based on frame width
    OWNERSHIP_DURATION_THRESHOLD = 0.2  # Reduced for faster pairing
    
    DROP_VELOCITY_THRESHOLD = 5.0  # Increased for easier detection
    DROP_STATIONARY_DURATION = 0.8  # Reduced for faster detection
    
    PERSON_DISAPPEAR_TIMEOUT = 2.0  # seconds
    
    def __init__(self, camera_id=1, bin_polygons=None):
        self.camera_id = camera_id
        
        # Track storage
        self.person_tracks: dict[int, PersonTrack] = {}
        self.object_tracks: dict[int, ObjectTrack] = {}
        
        # Bin zones
        self.bin_zones: List[Tuple[str, str, Polygon]] = []
        if bin_polygons:
            self._parse_zones(bin_polygons)
        
        self.frame_counter = 0
    
    def _parse_zones(self, zones_data):
        """Parse bin zone data into Polygon objects"""
        self.bin_zones = []
        for z in zones_data:
            if isinstance(z, Polygon):
                self.bin_zones.append(('Bin', 'general', z))
            elif isinstance(z, dict):
                coords = json.loads(z['coordinates']) if isinstance(z['coordinates'], str) else z['coordinates']
                self.bin_zones.append((z['label'], z.get('zone_type', 'general'), Polygon(coords)))
            elif isinstance(z, list):
                self.bin_zones.append(('Bin', 'general', Polygon(z)))
        
        print(f"[ZONES] Loaded {len(self.bin_zones)} bin zones")
    
    def update(self, person_tracks_raw, object_tracks_raw, frame_shape, frame=None, face_system=None):
        """
        Main update loop called every frame.
        """
        self.frame_counter += 1
        current_time = time.time()
        
        # Dynamic Threshold Calculation
        frame_width = frame_shape[1] if frame_shape else 1280
        # ownership threshold: 15% of frame width (e.g. 192px for 1280w)
        ownership_dist_thresh = max(150, frame_width * 0.15)
        # drop distance: slightly larger than ownership
        drop_dist_thresh = ownership_dist_thresh * 1.2  # Reduced from 1.5 to make drop easier
        
        # ────────────────────────────────────────────
        # STEP 1: Update Person Tracks
        # ────────────────────────────────────────────
        active_person_ids = set()
        for p_raw in person_tracks_raw:
            track_id = p_raw['track_id']
            active_person_ids.add(track_id)
            
            # Get user_id from face system (generic, no hardcoding)
            user_id = None
            if face_system:
                user_id = face_system.get_user_id(track_id)
            
            if track_id not in self.person_tracks:
                self.person_tracks[track_id] = PersonTrack(
                    track_id=track_id,
                    user_id=user_id
                )
                if user_id:
                    print(f"[TRACK] person_track={track_id} user_id={user_id}")
                else:
                    print(f"[TRACK] person_track={track_id} user_id=Unknown")
            
            person = self.person_tracks[track_id]
            person.update_position(p_raw['bbox'])
            
            # Update user_id if it changed (face recognition may take time)
            if user_id and person.user_id != user_id:
                person.user_id = user_id
                print(f"[TRACK] person_track={track_id} user_id={user_id} (updated)")
        
        # ────────────────────────────────────────────
        # STEP 2: Update Object Tracks
        # ────────────────────────────────────────────
        active_object_ids = set()
        for o_raw in object_tracks_raw:
            track_id = o_raw['track_id']
            active_object_ids.add(track_id)
            
            if track_id not in self.object_tracks:
                self.object_tracks[track_id] = ObjectTrack(
                    track_id=track_id,
                    class_name=o_raw.get('class', 'object')
                )
                print(f"[TRACK] {o_raw.get('class', 'object')}_track={track_id}")
            
            obj = self.object_tracks[track_id]
            obj.update_position(o_raw['bbox'])
            obj.is_lost = False # Reset lost status if track found
            obj.lost_timestamp = None
        
        # ────────────────────────────────────────────
        # STEP 3: Ownership Assignment
        # ────────────────────────────────────────────
        for obj_id in active_object_ids:
            obj = self.object_tracks[obj_id]
            
            # Skip if already dropped or event generated
            if obj.dropped or obj.event_generated:
                continue
            
            # Find closest person
            closest_person = None
            min_distance = float('inf')
            
            for person_id in active_person_ids:
                person = self.person_tracks[person_id]
                distance = obj.distance_to(person)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_person = person
            
            # Check ownership conditions
            if closest_person:
                is_inside = closest_person.is_point_inside(obj.centroid)
                
                # IMMEDIATE OWNERSHIP if inside person's bounding box
                if is_inside:
                    if obj.owner_person_track_id is None:
                        obj.owner_person_track_id = closest_person.track_id
                        obj.owner_user_id = closest_person.user_id
                        closest_person.active_object_ids.add(obj_id)
                        user_str = f"user_id={closest_person.user_id}" if closest_person.user_id else "user_id=Unknown"
                        print(f"[OWNERSHIP] object {obj_id} → person {closest_person.track_id} ({user_str}) [IMMEDIATE - INSIDE]")
                elif min_distance < ownership_dist_thresh:
                    if obj.owner_person_track_id is None:
                        # Start tracking proximity
                        if obj.possession_start_timestamp is None:
                            obj.possession_start_timestamp = current_time
                        
                        # Check duration threshold
                        duration = current_time - obj.possession_start_timestamp
                        if duration >= self.OWNERSHIP_DURATION_THRESHOLD:
                            # Assign ownership
                            obj.owner_person_track_id = closest_person.track_id
                            obj.owner_user_id = closest_person.user_id
                            closest_person.active_object_ids.add(obj_id)
                            
                            user_str = f"user_id={closest_person.user_id}" if closest_person.user_id else "user_id=Unknown"
                            print(f"[OWNERSHIP] object {obj_id} → person {closest_person.track_id} ({user_str}) [DISTANCE]")
                elif min_distance < ownership_dist_thresh * 2:
                    # Debug log for near misses (every 60 frames)
                    if self.frame_counter % 60 == 0:
                        print(f"[DEBUG] Near Miss: Obj {obj_id} is {int(min_distance)}px from Person {closest_person.track_id} (Thresh: {int(ownership_dist_thresh)})")
                
                # Reset if moved away (and not owned)
                if min_distance >= ownership_dist_thresh and obj.owner_person_track_id is None:
                    obj.possession_start_timestamp = None
        
        # ────────────────────────────────────────────
        # STEP 4: Drop Detection
        # ────────────────────────────────────────────
        for obj_id in active_object_ids:
            obj = self.object_tracks[obj_id]
            
            # Only check owned objects that haven't dropped yet
            if obj.owner_person_track_id is None or obj.dropped or obj.event_generated:
                continue
            
            # Check if owner still exists
            owner = self.person_tracks.get(obj.owner_person_track_id)
            if not owner:
                continue
            
            distance = obj.distance_to(owner)
            
            # Check drop conditions
            if distance > drop_dist_thresh:
                # Object separated from owner
                if obj.velocity < self.DROP_VELOCITY_THRESHOLD:
                    # Object is moving slowly (nearly stationary)
                    if obj.stationary_start is None:
                        obj.stationary_start = current_time
                        print(f"[DEBUG] Drop Candidate: Obj {obj_id} separated ({int(distance)}px). Timer Started.")
                    
                    stationary_duration = current_time - obj.stationary_start
                    if stationary_duration >= 0.5: # Reduced from DROP_STATIONARY_DURATION for snappier response
                        # DROP DETECTED
                        obj.dropped = True
                        obj.drop_centroid = obj.centroid
                        obj.drop_timestamp = current_time
                        
                        # Remove from owner's active objects
                        owner.active_object_ids.discard(obj_id)
                        
                        user_str = f"user_id={obj.owner_user_id}" if obj.owner_user_id else "user_id=Unknown"
                        print(f"[DROP] object {obj_id} released ({user_str})")
                else:
                    # Object is still moving fast, reset timer
                    if self.frame_counter % 30 == 0:
                        print(f"[DEBUG] Obj {obj_id} separated ({int(distance)}px) but moving too fast ({int(obj.velocity)} > {self.DROP_VELOCITY_THRESHOLD})")
                    obj.stationary_start = None
            else:
                # Object still close to owner, reset drop detection
                if self.frame_counter % 30 == 0:
                     print(f"[DEBUG] Obj {obj_id} Owned but close: {int(distance)}px < {int(drop_dist_thresh)}px")
                obj.stationary_start = None
        
        # ────────────────────────────────────────────
        # STEP 5: Disposal Classification & Event Generation
        # ────────────────────────────────────────────
        for obj_id in list(self.object_tracks.keys()):
            obj = self.object_tracks[obj_id]
            
            # Only process dropped objects that haven't generated events
            if not obj.dropped or obj.event_generated:
                continue
            
            # Classify disposal
            is_in_bin = self._check_point_in_bins(obj.drop_centroid)
            disposal_type = "PROPER_DISPOSAL" if is_in_bin else "VIOLATION"
            
            zone_status = "inside bin" if is_in_bin else "outside bin"
            user_str = f"user_id={obj.owner_user_id}" if obj.owner_user_id else "user_id=Unknown"
            print(f"[ZONE] {zone_status}")
            print(f"[EVENT] {disposal_type.lower()} {user_str} object={obj_id}")
            
            # Capture evidence
            evidence_filename = None
            if frame is not None:
                evidence_filename = f"event_{int(obj.drop_timestamp)}_{obj_id}.jpg"
                self._capture_evidence(frame, obj.bbox, evidence_filename)
            
            # Generate event
            self._generate_event(
                obj=obj,
                disposal_type=disposal_type,
                evidence_filename=evidence_filename
            )
            
            obj.event_generated = True
        
        # ────────────────────────────────────────────
        # STEP 6: Cleanup
        # ────────────────────────────────────────────
        # Remove person tracks that disappeared
        for person_id in list(self.person_tracks.keys()):
            if person_id not in active_person_ids:
                person = self.person_tracks[person_id]
                if current_time - person.last_seen > self.PERSON_DISAPPEAR_TIMEOUT:
                    # Release owned objects if person disappeared
                    for obj_id in person.active_object_ids:
                        if obj_id in self.object_tracks:
                            obj = self.object_tracks[obj_id]
                            if not obj.dropped and not obj.event_generated:
                                # DISAPPEARANCE LOGIC: If person disappears, object is "dropped" at last known spot
                                obj.dropped = True
                                obj.drop_centroid = obj.centroid
                                obj.drop_timestamp = current_time
                                print(f"[DROP] object {obj_id} released (owner disappeared)")
                    
                    del self.person_tracks[person_id]
        
        # Remove confirmed objects after a delay
        for obj_id in list(self.object_tracks.keys()):
            if obj_id not in active_object_ids:
                obj = self.object_tracks[obj_id]
                
                # PERSISTENT TRACKING: If owned object is lost but owner is still active
                if obj.owner_person_track_id is not None and not obj.dropped and not obj.event_generated:
                    owner = self.person_tracks.get(obj.owner_person_track_id)
                    if owner and owner.track_id in active_person_ids:
                        # Owner is still here, check if it was lost in a bin
                        if self._check_point_in_bins(obj.centroid):
                            # Object lost inside bin -> Proper Disposal
                            obj.dropped = True
                            obj.drop_centroid = obj.centroid
                            obj.drop_timestamp = current_time
                            print(f"[DROP] object {obj_id} lost inside bin (owner still present)")
                        else:
                            # Not in bin, owner still here -> Anchor to owner
                            obj.centroid = owner.centroid
                            obj.is_lost = True
                            if obj.lost_timestamp is None:
                                obj.lost_timestamp = current_time
                            # (Wait for owner to leave before counting as violation)
                            continue
                
                # If unowned or owner also gone, trigger drop
                if obj.owner_person_track_id is not None and not obj.dropped and not obj.event_generated:
                    # Check if owner also disappeared
                    owner_still_exists = obj.owner_person_track_id in active_person_ids
                    if not owner_still_exists:
                        obj.dropped = True
                        obj.drop_centroid = obj.centroid
                        obj.drop_timestamp = current_time
                        print(f"[DROP] object {obj_id} lost and owner gone.")
                
                # Keep in memory briefly for event generation
                if obj.event_generated:
                    del self.object_tracks[obj_id]
                elif not obj.dropped and not obj.owner_person_track_id:
                    # Clean up unowned, non-dropped tracks that were lost
                    del self.object_tracks[obj_id]
                elif obj.dropped and not obj.event_generated:
                    # Event generation happens in Step 5, don't delete yet
                    pass
    
    def _check_point_in_bins(self, point: Tuple[float, float]) -> bool:
        """Check if a point is inside any bin zone (with a small buffer)"""
        if not point:
            return False
        
        pt = Point(point)
        # 50 pixel buffer around the bin zone to account for perspective/lag
        buffer_size = 50 
        
        for label, zone_type, polygon in self.bin_zones:
            # Check main polygon
            if polygon.contains(pt):
                return True
            
            # Check buffered polygon (distance 50px)
            if polygon.buffer(buffer_size).contains(pt):
                print(f"[DEBUG] Buffer Match: Point {point} is near Bin {label}")
                return True
                
        return False
    
    def _capture_evidence(self, frame, bbox, filename):
        """Capture evidence image of the disposal"""
        try:
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = map(int, bbox)
            pad = 150
            crop = frame[max(0, y1-pad):min(h, y2+pad), max(0, x1-pad):min(w, x2+pad)]
            
            # Use absolute path
            base_dir = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "backend", "app", "static", "images"
            ))
            os.makedirs(base_dir, exist_ok=True)
            save_path = os.path.join(base_dir, filename)
            
            cv2.imwrite(save_path, crop)
            print(f"[EVIDENCE] Captured: {filename}")
        except Exception as e:
            print(f"[EVIDENCE] Capture failed: {e}")
    
    def _generate_event(self, obj: ObjectTrack, disposal_type: str, evidence_filename: Optional[str]):
        """
        Generate disposal event and send to backend.
        
        CRITICAL: This generates exactly ONE event per object track.
        No duplicates allowed.
        """
        payload = {
            "event_type": disposal_type.lower(),
            "confidence": 0.95,
            "camera_id": self.camera_id,
            "user_id": obj.owner_user_id,  # Nullable, backend handles Unknown
            "image_path": evidence_filename,
            "telemetry": {
                "object_type": obj.class_name,
                "object_track_id": obj.track_id,
                "trajectory": obj.trajectory,
                "drop_timestamp": obj.drop_timestamp
            }
        }
        
        # Async POST to prevent blocking CV pipeline
        def _post():
            try:
                response = requests.post(f"{API_URL}/events/", json=payload, timeout=3)
                if response.status_code == 200:
                    print(f"[API] Event saved: object={obj.track_id}")
                else:
                    print(f"[API] Event failed: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"[API] Event error: {e}")
        
        threading.Thread(target=_post, daemon=True).start()
