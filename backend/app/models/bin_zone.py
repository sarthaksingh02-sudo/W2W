from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum as SqlEnum
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class ZoneType(str, enum.Enum):
    GENERAL = "general"
    RECYCLE = "recycle"
    ORGANIC = "organic"
    E_WASTE = "e-waste"

class BinZone(Base):
    __tablename__ = "bin_zones"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, nullable=True)  # Made nullable
    label = Column(String) # e.g. "Primary Garbage"
    zone_type = Column(String, default="general")  # Simplified to String
    coordinates = Column(Text) # JSON string of 4 polygon points "[[x,y], [x,y], [x,y], [x,y]]"
