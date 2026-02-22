from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class UserBase(BaseModel):
    name: str
    role: str = "resident"
    flat_number: Optional[str] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class EventBase(BaseModel):
    event_type: str
    confidence: float
    camera_id: int
    user_id: Optional[int] = None
    image_path: Optional[str] = None
    telemetry: Optional[Any] = None # JSON dict

class EventCreate(EventBase):
    pass

class Event(EventBase):
    id: int
    timestamp: datetime
    class Config:
        from_attributes = True

class CameraBase(BaseModel):
    name: str
    rtsp_url: str
    location: str
    is_active: bool = True

class CameraCreate(CameraBase):
    pass

class Camera(CameraBase):
    id: int
    class Config:
        from_attributes = True
class BinZoneBase(BaseModel):
    camera_id: int
    label: str
    zone_type: str = "general"
    coordinates: str # JSON string

class BinZoneCreate(BinZoneBase):
    pass

class BinZone(BinZoneBase):
    id: int
    class Config:
        from_attributes = True
