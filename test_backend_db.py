"""
Diagnostic script to test database connectivity and model loading
"""
import sys
import traceback

print("=" * 60)
print("ECOPE Backend Diagnostic")
print("=" * 60)

# Test 1: Database Connection
print("\n[1/5] Testing database connection...")
try:
    from backend.app.database import engine, get_db
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        print(f"✓ Database connected successfully (result={result})")
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    traceback.print_exc()

# Test 2: Import Models
print("\n[2/5] Testing model imports...")
try:
    from backend.app.models import models
    from backend.app.models.bin_zone import BinZone
    print(f"✓ Models imported successfully")
    print(f"  - BinZone table: {BinZone.__tablename__}")
except Exception as e:
    print(f"✗ Model import failed: {e}")
    traceback.print_exc()

# Test 3: Create Tables
print("\n[3/5] Testing table creation...")
try:
    from backend.app.database import Base, engine
    Base.metadata.create_all(bind=engine)
    print(f"✓ Tables created/verified")
except Exception as e:
    print(f"✗ Table creation failed: {e}")
    traceback.print_exc()

# Test 4: Query BinZones
print("\n[4/5] Testing BinZone query...")
try:
    from backend.app.database import get_db
    from backend.app.models.bin_zone import BinZone
    db = next(get_db())
    zones = db.query(BinZone).all()
    print(f"✓ BinZone query successful: {len(zones)} zones found")
except Exception as e:
    print(f"✗ BinZone query failed: {e}")
    traceback.print_exc()

# Test 5: Test Zone Creation
print("\n[5/5] Testing zone creation...")
try:
    from backend.app.database import get_db
    from backend.app.models.bin_zone import BinZone
    import json
    
    db = next(get_db())
    test_zone = BinZone(
        camera_id=1,
        label="Test Zone",
        zone_type="general",
        coordinates=json.dumps([[0, 0], [100, 0], [100, 100], [0, 100]])
    )
    db.add(test_zone)
    db.commit()
    db.refresh(test_zone)
    print(f"✓ Test zone created with ID: {test_zone.id}")
    
    # Cleanup
    db.delete(test_zone)
    db.commit()
    print(f"✓ Test zone deleted")
except Exception as e:
    print(f"✗ Zone creation failed: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("Diagnostic complete")
print("=" * 60)
