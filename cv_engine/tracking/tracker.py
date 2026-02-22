import supervision as sv
import numpy as np
import time
import math

class ObjectTracker:
    def __init__(self, frame_rate=30):
        """
        Persistent Tracking System using ByteTrack.
        Stores trajectories, calculates velocities, and manages track lifespans.
        """
        self.tracker = sv.ByteTrack(
            frame_rate=frame_rate,
            track_activation_threshold=0.25,
            lost_track_buffer=30, # Lifespan/Occlusion Recovery (frames)
            minimum_matching_threshold=0.8
        )
        
        # Track Internal Storage
        # track_id -> { trajectory: [], last_seen: time }
        self.track_data = {}
        self.COCO_CLASSES = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", 
                            "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", 
                            "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", 
                            "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", 
                            "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", 
                            "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", 
                            "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", 
                            "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", 
                            "scissors", "teddy bear", "hair drier", "toothbrush"]

    def update(self, frame, detections_list):
        """
        Update tracking state and return JSON-formatted detections.
        """
        if not detections_list:
             return []

        detections_np = np.array(detections_list)
        
        # 1. ByteTrack Update
        xyxy = detections_np[:, :4]
        confidence = detections_np[:, 4]
        class_id = detections_np[:, 5].astype(int)

        detections = sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            class_id=class_id
        )

        tracks = self.tracker.update_with_detections(detections)
        
        # 2. Post-Process and Store Track Data
        output = []
        current_active_ids = []
        
        for xyxy, mask, confidence, cls_id, track_id, data in tracks:
            if track_id is None: continue
            
            current_active_ids.append(track_id)
            x1, y1, x2, y2 = map(int, xyxy)
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            
            # Initialize or update trajectory
            if track_id not in self.track_data:
                self.track_data[track_id] = {
                    "trajectory": [],
                    "velocity": 0.0,
                    "last_seen": time.time()
                }
            
            track_entry = self.track_data[track_id]
            track_entry["trajectory"].append((cx, cy))
            if len(track_entry["trajectory"]) > 30: 
                track_entry["trajectory"].pop(0)
            
            # Calculate Velocity (Pixels/Frame simple average over last 5 frames)
            if len(track_entry["trajectory"]) > 2:
                p1 = track_entry["trajectory"][-2]
                p2 = track_entry["trajectory"][-1]
                v = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                track_entry["velocity"] = v
            
            track_entry["last_seen"] = time.time()
            
            # 3. Format Output Requirement
            output.append({
                "track_id": int(track_id),
                "class": self.COCO_CLASSES[cls_id] if cls_id < len(self.COCO_CLASSES) else f"Obj {cls_id}",
                "bbox": [x1, y1, x2, y2],
                "centroid": [cx, cy],
                "velocity": float(track_entry["velocity"]),
                "timestamp": float(track_entry["last_seen"])
            })

        # Cleanup lost tracks from storage after timeout
        for tid in list(self.track_data.keys()):
            if time.time() - self.track_data[tid]["last_seen"] > 10.0: # 10s timeout
                del self.track_data[tid]

        return output
