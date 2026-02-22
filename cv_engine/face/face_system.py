from insightface.app import FaceAnalysis
import numpy as np
import cv2
import pickle
import os
import time
from collections import deque, Counter
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# --- Database Integration ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "ecope_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "ecope_secure_password")
DB_NAME = os.getenv("DB_NAME", "ecope_production")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

class FaceSystem:
    def __init__(self, gpu_id=0):
        """
        Face Recognition System using InsightFace Buffalo_L.
        Requirements: GPU execution, 30-frame rolling buffer, temporal mean similarity matching.
        """
        # 1. Initialize InsightFace with GPU priority
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            
            if 'CUDAExecutionProvider' in providers:
                # Test if it actually works (checks for DLLs)
                try:
                    test_session = ort.InferenceSession(None, providers=['CUDAExecutionProvider'])
                except:
                    print("[FaceSystem] CUDA found but missing libraries (DLLs). Falling back to CPU...")
                    providers = ['CPUExecutionProvider']
            else:
                providers = ['CPUExecutionProvider']

            self.app = FaceAnalysis(name='buffalo_l', providers=providers, allowed_modules=['detection', 'recognition'])
            self.gpu_id = gpu_id if 'CUDAExecutionProvider' in providers else -1
            self.app.prepare(ctx_id=self.gpu_id, det_size=(640, 640))
            print(f"[FaceSystem] InsightFace initialized on {'GPU' if self.gpu_id >=0 else 'CPU'}")
        except Exception as e:
            print(f"[FaceSystem] Initialization failed: {e}")
            self.app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'], allowed_modules=['detection', 'recognition'])
            self.gpu_id = -1
            self.app.prepare(ctx_id=self.gpu_id, det_size=(640, 640))

        # 2. Recognition Memory
        # track_id -> deque of embeddings (max 30)
        self.embedding_buffers = {} 
        # track_id -> { "user_id": int, "name": str, "confidence": float }
        self.locked_identities = {}
        
        # 3. Database Sync
        self.engine = create_engine(DATABASE_URL)
        self.known_faces = [] # List of { "user_id": int, "name": str, "embedding": np.array }
        self._load_known_faces()

    def _load_known_faces(self):
        """Sync known users and embeddings from PostgreSQL."""
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT u.id, u.name, f.embedding 
                    FROM users u 
                    JOIN face_embeddings f ON u.id = f.user_id
                """)
                result = conn.execute(query)
                self.known_faces = []
                for row in result:
                    emb = pickle.loads(row[2])
                    self.known_faces.append({
                        "user_id": row[0],
                        "name": row[1],
                        "embedding": emb / np.linalg.norm(emb) # Pre-normalize for cosine sim
                    })
                print(f"[FaceSystem] Loaded {len(self.known_faces)} known faces from database.")
        except Exception as e:
            print(f"[FaceSystem] Failed to load faces: {e}")

    def recognize(self, frame, tracks):
        """
        Main interface for processing tracks.
        Only processes 'person' tracks that aren't already locked.
        """
        for track in tracks:
            # Requirements: Only run for tracks with class == "person"
            if track.get("class") != "person":
                continue
            
            track_id = track["track_id"]
            
            # Identity Lock: Stop re-evaluating if consensus reached
            if track_id in self.locked_identities:
                continue

            # Extract face inside person bounding box
            bbox = track["bbox"]
            face_crop = self._get_face_crop(frame, bbox)
            if face_crop is None:
                continue

            # Generate Embedding
            # We run detection inside the person crop to accurately locate the face
            faces = self.app.get(face_crop)
            if not faces:
                continue

            # Select the most prominent face in the person bbox
            face = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0]) * (x.bbox[3]-x.bbox[1]))
            embedding = face.embedding / np.linalg.norm(face.embedding)

            # Store in rolling buffer (buffer_size = 30)
            if track_id not in self.embedding_buffers:
                self.embedding_buffers[track_id] = deque(maxlen=30)
            
            self.embedding_buffers[track_id].append(embedding)

            # Evaluate Consensus (min_frames = 10)
            if len(self.embedding_buffers[track_id]) >= 10:
                self._evaluate_identity(track_id)

    def _get_face_crop(self, frame, person_bbox):
        """Standardized face extraction with padding."""
        x1, y1, x2, y2 = map(int, person_bbox)
        h, w = frame.shape[:2]
        
        # Person bounding box is usually tall, face is in the top third
        # We take the top 50% of the person box for face searching
        face_zone_height = int((y2 - y1) * 0.5)
        
        # Add some wiggle room
        x1 = max(0, x1 - 10)
        y1 = max(0, y1 - 10)
        x2 = min(w, x2 + 10)
        crop_y2 = min(h, y1 + face_zone_height)
        
        crop = frame[y1:crop_y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
            return None
        return crop

    def _evaluate_identity(self, track_id):
        """
        Implementation of:
        - Highest mean similarity matching
        - 70% consensus threshold locking
        """
        buffer = list(self.embedding_buffers[track_id])
        if not self.known_faces:
            return

        # 1. Matching: Select highest mean similarity
        user_scores = []
        for user in self.known_faces:
            # Cosine similarity matrix: (len(buffer)) x (1)
            # Dot product since pre-normalized
            sims = [np.dot(emb, user["embedding"]) for emb in buffer]
            mean_sim = np.mean(sims)
            user_scores.append({
                "user_id": user["user_id"],
                "name": user["name"],
                "mean_sim": mean_sim,
                "frame_sims": sims
            })

        # Best candidate by highest mean similarity
        best_candidate = max(user_scores, key=lambda x: x["mean_sim"])
        
        # 2. Consensus Logic: 70% threshold
        # Count how many frames in the buffer had THIS candidate as the top match individual frame-wise
        top_match_counts = 0
        for i in range(len(buffer)):
            frame_scores = [(u["user_id"], u["frame_sims"][i]) for u in user_scores]
            top_user_idx, top_sim = max(frame_scores, key=lambda x: x[1])
            
            # Simple confidence gating for individual frames (e.g. 0.35)
            if top_user_idx == best_candidate["user_id"] and top_sim > 0.35:
                top_match_counts += 1
        
        consensus = top_match_counts / len(buffer)

        # 3. Identity Lock: consensus_threshold = 70%
        # Threshold: Best mean similarity must also be reasonable (> 0.4 usually)
        if best_candidate["mean_sim"] > 0.4 and consensus >= 0.70:
            self.locked_identities[track_id] = {
                "track_id": track_id,
                "user_id": best_candidate["user_id"],
                "name": best_candidate["name"],
                "confidence": float(best_candidate["mean_sim"])
            }
            print(f"[FaceSystem] IDENTITY LOCKED: #{track_id} -> {best_candidate['name']} ({consensus*100:.1f}% consensus)")

    def get_track_result(self, track_id):
        """
        Returns required dictionary format.
        {
          "track_id": int,
          "user_id": int | null,
          "name": str | "Unknown",
          "confidence": float
        }
        """
        if track_id in self.locked_identities:
            return self.locked_identities[track_id]
        
        # If not locked, return Unknown or current best guess (non-locked)
        return {
            "track_id": track_id,
            "user_id": None,
            "name": "Unknown",
            "confidence": 0.0
        }

    def get_identity(self, track_id):
        """Backwards compatibility for orchestrator."""
        res = self.get_track_result(track_id)
        if res["name"] == "Unknown" and track_id in self.embedding_buffers:
            return "Scanning..."
        return res["name"]

    def get_user_id(self, track_id):
        """Returns the PostgreSQL user_id if locked, else None."""
        res = self.get_track_result(track_id)
        return res.get("user_id")

    def clean_memory(self, active_track_ids):
        """Cleanup for tracks no longer in frame."""
        for tid in list(self.embedding_buffers.keys()):
            if tid not in active_track_ids:
                del self.embedding_buffers[tid]
        
        for tid in list(self.locked_identities.keys()):
            # We can either persist locks or clear them. 
            # ByteTrack handles re-ID, so if the ID is gone, the person is gone.
            if tid not in active_track_ids:
                 del self.locked_identities[tid]
