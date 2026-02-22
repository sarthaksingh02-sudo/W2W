from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.bin_zone import BinZone, ZoneType
from ..schemas import schemas

router = APIRouter(tags=["Zones"])

@router.post("/", response_model=schemas.BinZone)
def create_zone(zone: schemas.BinZoneCreate, db: Session = Depends(get_db)):
    db_zone = BinZone(**zone.dict())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone

@router.get("/", response_model=List[schemas.BinZone])
def read_zones(camera_id: int = None, db: Session = Depends(get_db)):
    query = db.query(BinZone)
    if camera_id:
        query = query.filter(BinZone.camera_id == camera_id)
    return query.all()

@router.delete("/{zone_id}")
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    db_zone = db.query(BinZone).filter(BinZone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    db.delete(db_zone)
    db.commit()
    return {"message": "Zone deleted"}
