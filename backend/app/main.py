from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List
import shutil
import os
import json

from .database import engine, Base, get_db
from .models import models
from .schemas import schemas

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ECOPE API", version="1.0.0", redirect_slashes=False)

# Mount Static Files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static", "images")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/images", StaticFiles(directory=STATIC_DIR), name="images")

from .models.bin_zone import BinZone, ZoneType

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/zones/", response_model=schemas.BinZone)
def create_zone(zone: schemas.BinZoneCreate, db: Session = Depends(get_db)):
    db_zone = BinZone(**zone.dict())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone

@app.get("/zones/", response_model=List[schemas.BinZone])
def read_zones(camera_id: int = None, db: Session = Depends(get_db)):
    try:
        query = db.query(BinZone)
        if camera_id:
            query = query.filter(BinZone.camera_id == camera_id)
        result = query.all()
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/zones/{zone_id}")
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    db_zone = db.query(BinZone).filter(BinZone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    db.delete(db_zone)
    db.commit()
    return {"message": "Zone deleted"}

# --- Routes ---

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = models.User(name=user.name, role=user.role, flat_number=user.flat_number)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/", response_model=List[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

from .utils.face_utils import get_embedding_from_bytes

@app.post("/register/")
async def register_user(
    name: str = Form(...),
    role: str = Form(...),
    flat_number: str = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    # 1. Create User
    db_user = models.User(name=name, role=role, flat_number=flat_number)
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="User already exists or DB Error")

    # 2. Process Images
    valid_samples = 0
    for file in files:
        content = await file.read()
        embedding_pickle = get_embedding_from_bytes(content)
        
        if embedding_pickle:
            db_emb = models.FaceEmbedding(user_id=db_user.id, embedding=embedding_pickle)
            db.add(db_emb)
            valid_samples += 1
    
    if valid_samples == 0:
        # Rolback user if no valid faces
        db.delete(db_user)
        db.commit()
        raise HTTPException(status_code=400, detail="No valid faces detected in samples.")
        
    db.commit()
    return {"message": f"User {name} registered with {valid_samples} face samples."}

@app.on_event("startup")
def startup_event():
    # Ensure default camera exists
    db = next(get_db())
    cam = db.query(models.Camera).filter(models.Camera.id == 1).first()
    if not cam:
        print("Creating default camera #1")
        default_cam = models.Camera(id=1, name="Entrance Camera", location="Main Entrance")
        db.add(default_cam)
        db.commit()

@app.post("/events/", response_model=schemas.Event)
async def create_event(event: schemas.EventCreate, db: Session = Depends(get_db)):
    try:
        event_data = event.dict()
        if isinstance(event_data.get('telemetry'), (dict, list)):
            event_data['telemetry'] = json.dumps(event_data['telemetry'])
            
        db_event = models.Event(**event_data)
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        
        # Enrich for WS
        user_name = "Unknown"
        if db_event.user_id:
            u = db.query(models.User).filter(models.User.id == db_event.user_id).first()
            if u: user_name = u.name
            
        camera_name = "Unknown"
        if db_event.camera_id:
            c = db.query(models.Camera).filter(models.Camera.id == db_event.camera_id).first()
            if c: camera_name = c.name
            
        # Broadcast to WS (Flat format for Dashboard.jsx)
        ws_msg = {
            "type": db_event.event_type.value if hasattr(db_event.event_type, 'value') else db_event.event_type,
            "timestamp": db_event.timestamp.isoformat(),
            "camera": db_event.camera_id,
            "user": user_name,
            "confidence": db_event.confidence,
            "image_path": db_event.image_path
        }
        await manager.broadcast(json.dumps(ws_msg))
        
        return db_event
    except Exception as e:
        print(f"Error creating event: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

from datetime import date, datetime
from typing import Optional

@app.get("/events/", response_model=List[schemas.Event])
def read_events(
    skip: int = 0, 
    limit: int = 100, 
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Event)
    
    if user_id:
        query = query.filter(models.Event.user_id == user_id)
    if event_type:
        query = query.filter(models.Event.event_type == event_type)
    if start_date:
        query = query.filter(models.Event.timestamp >= start_date)
    if end_date:
        # Include the whole end date
        query = query.filter(models.Event.timestamp < end_date + datetime.timedelta(days=1))

    events = query.order_by(models.Event.timestamp.desc()).offset(skip).limit(limit).all()
    return events

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or process client messages if needed
    except Exception:
        manager.disconnect(websocket)
