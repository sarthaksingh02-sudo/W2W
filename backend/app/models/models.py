from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, LargeBinary, Enum as SqlEnum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base

class EventType(str, enum.Enum):
    VIOLATION = "violation"
    PROPER_DISPOSAL = "proper_disposal"
    SYSTEM = "system"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    role = Column(String, default="resident") # resident, staff, admin
    flat_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    events = relationship("Event", back_populates="user")
    embeddings = relationship("FaceEmbedding", back_populates="user")

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    embedding = Column(LargeBinary) # Serialized numpy array
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="embeddings")

class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    rtsp_url = Column(String)
    location = Column(String)
    is_active = Column(Boolean, default=True)

    events = relationship("Event", back_populates="camera")

from .bin_zone import BinZone, ZoneType

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(SqlEnum(EventType)) # VIOLATION / PROPER_DISPOSAL
    timestamp = Column(DateTime, default=func.now())
    confidence = Column(Float)
    image_path = Column(String)
    
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Nullable for 'Unknown'
    telemetry = Column(Text, nullable=True) # JSON string for trajectory/obj_type
    
    camera = relationship("Camera", back_populates="events")
    user = relationship("User", back_populates="events")

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String)
    message = Column(String)
    created_at = Column(DateTime, default=func.now())
