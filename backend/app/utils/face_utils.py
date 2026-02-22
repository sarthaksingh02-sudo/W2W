from insightface.app import FaceAnalysis
import numpy as np
import cv2
import pickle
import os

# Initialize InsightFace statically to avoid reloading on every request
# NOTE: This consumes GPU VRAM. Ensure GPU_ID is correct.
GPU_ID = int(os.getenv("GPU_ID", 0))
providers = ['CUDAExecutionProvider'] if GPU_ID >= 0 else ['CPUExecutionProvider']
app = FaceAnalysis(name='buffalo_l', providers=providers, allowed_modules=['detection', 'recognition'])
app.prepare(ctx_id=GPU_ID, det_size=(640, 640))

def get_embedding_from_bytes(image_bytes):
    """
    Decodes image bytes and returns the face embedding.
    Returns None if no face or multiple faces found (strict mode for registration).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        return None

    faces = app.get(img)
    
    # Validation: Must detect exactly one face for registration sample
    if len(faces) != 1:
        return None
        
    # Return the embedding
    return pickle.dumps(faces[0].embedding)
