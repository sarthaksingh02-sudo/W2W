import cv2
import time
import os
import signal
import sys
import threading
import flask
import numpy as np
from dotenv import load_dotenv
from shapely.geometry import Polygon
import requests
import json

# Add Project Root to Path to allow direct execution
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cv_engine.stream.video_source import FFmpegVideoSource
from cv_engine.detection.detector import ObjectDetector
from cv_engine.tracking.tracker import ObjectTracker
from cv_engine.face.face_system import FaceSystem
from cv_engine.smoothing.smoother import TrackSmoother
from cv_engine.disposal.universal_fsm import UniversalAssociationSystem

# Load Config
load_dotenv()
RTSP_URL = os.getenv("RTSP_SOURCES", "").split(",")[0]
GPU_ID = int(os.getenv("GPU_ID", 0))

# Global State
latest_frame = None
lock = threading.Lock()
flask_app = flask.Flask(__name__)

# Zone Selection State
zone_points = []
API_URL = "http://localhost:8000"
CAMERA_ID = 1 # Default

def load_zone():
    global zone_points
    try:
        res = requests.get(f"{API_URL}/zones/?camera_id={CAMERA_ID}")
        if res.status_code == 200:
            zones = res.json()
            if zones:
                # For simplicity, we use the first zone for local display
                # In production, we'd handle multiple zones
                latest_z = zones[-1]
                zone_points = json.loads(latest_z['coordinates'])
                print(f"[Orchestrator] Loaded zone from DB: {zone_points}")
                return zones
    except Exception as e:
        print(f"[Orchestrator] DB Zone Load Error: {e}")
    return []

def save_zone():
    payload = {
        "camera_id": CAMERA_ID,
        "label": "General Bin",
        "zone_type": "general",
        "coordinates": json.dumps(zone_points)
    }
    try:
        res = requests.post(f"{API_URL}/zones/", json=payload, timeout=5)
        if res.status_code == 200:
            print(f"[Orchestrator] Zone saved to DB.")
        else:
            print(f"[Orchestrator] Failed to save zone: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[Orchestrator] DB Zone Save Error: {e}")

def mouse_callback(event, x, y, flags, param):
    global zone_points
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(zone_points) >= 4:
            zone_points = [] # Reset on 5th click
        zone_points.append([x, y])
        if len(zone_points) == 4:
            save_zone()

@flask_app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with lock:
                if latest_frame is None:
                    time.sleep(0.01)
                    continue
                (flag, encodedImage) = cv2.imencode(".jpg", latest_frame)
                if not flag: continue
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
            time.sleep(0.03)
    return flask.Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

def main():
    global latest_frame
    print(f"[Orchestrator] Starting ECOPE Engine...")
    print(f"[Orchestrator] Source: {RTSP_URL}")
    print(f"[Orchestrator] Starting MJPEG Stream on http://localhost:5000/video_feed")

    # Start Flask Thread
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    
    # 1. Initialize Components
    source = FFmpegVideoSource(source_id="cam_01", rtsp_url=RTSP_URL, gpu_id=GPU_ID)
    detector = ObjectDetector(model_path="yolov8n.pt", device=GPU_ID) 
    tracker = ObjectTracker()
    face_sys = FaceSystem(gpu_id=GPU_ID)
    smoother = TrackSmoother()
    
    # Load Saved Zones
    db_zones = load_zone()
    universal_system = UniversalAssociationSystem(camera_id=CAMERA_ID, bin_polygons=db_zones)

    source.start()
    cv2.namedWindow("ECOPE Production", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ECOPE Production", 1280, 720)
    cv2.setMouseCallback("ECOPE Production", mouse_callback)
    running = True

    try:
        while running:
            # 3. Ingestion
            ts, frame = source.read()
            if frame is None:
                time.sleep(0.01)
                continue

            # 4. Perception
            try:
                detections = detector.detect(frame)
                tracks = tracker.update(frame, detections)
                face_sys.recognize(frame, tracks)
                smoother.update(tracks)
                
                # Universal System Logic
                # Fetch zones periodically (every 100 frames)
                if universal_system.frame_counter % 100 == 0:
                    db_zones = load_zone()
                    universal_system._parse_zones(db_zones)

                person_tracks = [t for t in tracks if t["class"] == "person"]
                waste_tracks = [t for t in tracks if t["class"] != "person"]
                universal_system.update(person_tracks, waste_tracks, frame.shape, frame, face_system=face_sys)
                
            except Exception as e:
                print(f"Perception Error: {e}")
                tracks = [] # Fallback

            # Draw Bin Zone (locally we draw the current active selection)
            if len(zone_points) > 0:
                pts = np.array(zone_points, np.int32).reshape((-1, 1, 2))
                color = (0, 255, 255) if len(zone_points) == 4 else (255, 255, 0)
                cv2.polylines(frame, [pts], len(zone_points) == 4, color, 2)
                for p in zone_points:
                    cv2.circle(frame, tuple(p), 4, color, -1)
                if len(zone_points) == 4:
                    cv2.putText(frame, "Disposal Zone", tuple(zone_points[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            else:
                cv2.putText(frame, "Click 4 points to set Zone", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Draw Tracks
            for t in tracks:
                x1, y1, x2, y2 = map(int, t["bbox"])
                cls_name = t["class"]
                track_id = t["track_id"]
                
                if cls_name == "person":
                    identity = face_sys.get_identity(track_id)
                    color = (0, 255, 0)
                    label = f"#{track_id} {identity}"
                else:
                    color = (0, 0, 255)
                    label = f"{cls_name} #{track_id}"

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Update Global Frame for Stream
            with lock:
                latest_frame = frame.copy()
            
            # Local Display
            cv2.imshow("ECOPE Production", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("Stopping...")
    except Exception as e:
        print(f"[Orchestrator] Error: {e}")
    finally:
        source.stop()
        cv2.destroyAllWindows()
        print("[Orchestrator] Shutdown complete.")

if __name__ == "__main__":
    main()
