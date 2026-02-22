# Universal Object-Person-Event Association System

## Overview

This system implements a **universal, generic object tracking and disposal event system** that works automatically for **ALL registered users** without any hardcoding.

## Core Principle

```
NO USER NAMES IN CV ENGINE
ONLY: user_id, person_track_id, object_track_id
```

## Architecture

### Data Structures

#### PersonTrack
```python
@dataclass
class PersonTrack:
    track_id: int                    # ByteTrack ID
    user_id: Optional[int]           # From face recognition (nullable)
    bbox: Tuple[float, ...]          # Bounding box
    centroid: Tuple[float, float]    # Center point
    active_object_ids: Set[int]      # Objects currently owned
    last_seen: float                 # Timestamp
```

#### ObjectTrack
```python
@dataclass
class ObjectTrack:
    track_id: int                           # ByteTrack ID
    class_name: str                         # "bottle", "cup", etc.
    bbox: Tuple[float, ...]                 
    centroid: Tuple[float, float]
    trajectory: List[Tuple[float, float]]   # Movement history
    velocity: float                         # Current speed (px/frame)
    
    # Ownership
    owner_person_track_id: Optional[int]    # Who owns this
    owner_user_id: Optional[int]            # User ID of owner (nullable)
    possession_start_timestamp: Optional[float]
    
    # Drop state
    dropped: bool                           # Has been dropped
    drop_centroid: Optional[Tuple[float, float]]
    drop_timestamp: Optional[float]
    
    # Event tracking
    event_generated: bool                   # Prevents duplicates
```

## Processing Pipeline

### Frame N

```
1. Update Person Tracks
   ├─ Get detections from ByteTrack
   ├─ Query FaceSystem for user_id (generic)
   └─ Update PersonTrack.user_id (may be None)

2. Update Object Tracks
   ├─ Get detections from ByteTrack
   ├─ Calculate velocity
   └─ Update trajectory

3. Ownership Assignment
   ├─ For each object without owner:
   │  ├─ Find closest person
   │  ├─ Check distance < 100px
   │  ├─ Check overlap duration ≥ 0.5s
   │  └─ Assign: object.owner_user_id = person.user_id
   └─ Log: [OWNERSHIP] object X → person Y (user_id=Z)

4. Drop Detection
   ├─ For each owned object:
   │  ├─ Check distance from owner > 180px
   │  ├─ Check velocity < 2 px/frame
   │  ├─ Check stationary duration ≥ 1.0s
   │  └─ Mark: object.dropped = True
   └─ Log: [DROP] object X released (user_id=Y)

5. Disposal Classification
   ├─ For each dropped object (once):
   │  ├─ Check drop_centroid ∈ bin polygon
   │  ├─ Classify: PROPER_DISPOSAL or VIOLATION
   │  └─ Generate event
   └─ Log: [EVENT] violation user_id=X object=Y

6. Cleanup
   ├─ Remove disappeared persons
   └─ Remove confirmed events
```

## Ownership Rules

### Assignment Conditions

An object becomes owned when **ALL** of the following are true:

1. `distance(object, person) < 100 pixels`
2. `overlap_duration ≥ 0.5 seconds`
3. Both tracks are active simultaneously

### Ownership Persistence

Ownership persists through:
- Occlusion (person temporarily hidden)
- Brief separations (< 180px)
- Velocity changes

Ownership ends when:
- Object is dropped (distance > 180px AND stationary)
- Person disappears for > 2 seconds

## Drop Detection

An owned object is **dropped** when:

```python
distance(object, owner) > 180 px
AND velocity < 2 px/frame
AND stationary_duration ≥ 1.0 second
```

At drop moment:
1. Freeze ownership (owner_user_id locked)
2. Store drop_centroid
3. Mark dropped = True
4. Remove from person.active_object_ids

## Event Generation

### Schema

```json
{
  "event_type": "proper_disposal" | "violation",
  "confidence": 0.95,
  "camera_id": 1,
  "user_id": 123,              // Nullable (None for Unknown)
  "image_path": "event_12345_99.jpg",
  "telemetry": {
    "object_type": "bottle",
    "object_track_id": 99,
    "trajectory": [[x1, y1], [x2, y2], ...],
    "drop_timestamp": 1234567890.123
  }
}
```

### Deduplication

- **One event per object_track_id**
- `event_generated` flag prevents duplicates
- Events generated in `STEP 5` only

## Logging Format

### Required Logs

```
[TRACK] person_track=12 user_id=7
[TRACK] person_track=13 user_id=Unknown
[TRACK] bottle_track=42
[OWNERSHIP] object 42 → person 12 (user_id=7)
[DROP] object 42 released (user_id=7)
[ZONE] outside bin
[EVENT] violation user_id=7 object=42
[API] Event saved: object=42
```

## Example Scenarios

### Scenario 1: Registered User Litters

```
Frame 100:
  [TRACK] person_track=5 user_id=101
  [TRACK] bottle_track=20

Frame 120:
  [OWNERSHIP] object 20 → person 5 (user_id=101)

Frame 200:
  [DROP] object 20 released (user_id=101)
  [ZONE] outside bin
  [EVENT] violation user_id=101 object=20
  [API] Event saved: object=20
```

### Scenario 2: Unknown User Disposes Properly

```
Frame 50:
  [TRACK] person_track=7 user_id=Unknown
  [TRACK] cup_track=15

Frame 70:
  [OWNERSHIP] object 15 → person 7 (user_id=Unknown)

Frame 150:
  [DROP] object 15 released (user_id=Unknown)
  [ZONE] inside bin
  [EVENT] proper_disposal user_id=Unknown object=15
  [API] Event saved: object=15
```

### Scenario 3: Multiple Users Simultaneously

```
Frame 10:
  [TRACK] person_track=1 user_id=50
  [TRACK] person_track=2 user_id=75
  [TRACK] bottle_track=10
  [TRACK] can_track=11

Frame 30:
  [OWNERSHIP] object 10 → person 1 (user_id=50)
  [OWNERSHIP] object 11 → person 2 (user_id=75)

Frame 100:
  [DROP] object 10 released (user_id=50)
  [ZONE] inside bin
  [EVENT] proper_disposal user_id=50 object=10

Frame 120:
  [DROP] object 11 released (user_id=75)
  [ZONE] outside bin
  [EVENT] violation user_id=75 object=11
```

## Backend Integration

### Events Table

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR NOT NULL,  -- 'proper_disposal' or 'violation'
    timestamp TIMESTAMP DEFAULT NOW(),
    confidence FLOAT,
    camera_id INTEGER,
    user_id INTEGER NULLABLE,      -- NULL for Unknown users
    image_path VARCHAR,
    telemetry TEXT                 -- JSON string
);
```

### API Endpoint

```python
@app.post("/events/")
def create_event(event: EventCreate, db: Session):
    # Accept any user_id (including None)
    db_event = Event(**event.dict())
    db.add(db_event)
    db.commit()
    
    # Resolve user_id → name for WebSocket
    user_name = "Unknown"
    if event.user_id:
        user = db.query(User).filter(User.id == event.user_id).first()
        if user:
            user_name = user.name
    
    # Broadcast to frontend
    ws_manager.broadcast({
        "user": user_name,  # Resolved here, not in CV
        "type": event.event_type,
        ...
    })
    
    return db_event
```

## Frontend Display

```javascript
// Frontend receives:
{
  "user": "John Doe",      // Backend resolved user_id→name
  "type": "violation",
  "camera": "Gate 1",
  "timestamp": "2026-01-25 13:00:00",
  "image_path": "event_12345_99.jpg"
}

// Display:
<div class="event">
  <span class="user">{user || "Unknown"}</span>
  <span class="type">{type}</span>
  <img src={`/images/${image_path}`} />
</div>
```

## Testing

Run comprehensive tests:

```bash
python -m pytest tests/test_universal_fsm.py -v
```

### Test Coverage

- ✅ No hardcoded users
- ✅ Generic user_id handling
- ✅ Unknown user support
- ✅ Multi-user independence
- ✅ Event deduplication
- ✅ Data structure integrity

## Configuration

### Constants (Tunable)

```python
OWNERSHIP_DISTANCE_THRESHOLD = 100    # pixels
OWNERSHIP_DURATION_THRESHOLD = 0.5    # seconds
DROP_DISTANCE_THRESHOLD = 180         # pixels
DROP_VELOCITY_THRESHOLD = 2.0         # px/frame
DROP_STATIONARY_DURATION = 1.0        # seconds
PERSON_DISAPPEAR_TIMEOUT = 2.0        # seconds
```

## Migration from Old FSM

### Before (Hardcoded)
```python
if user_name == "sarthak":
    handle_specific_user()
```

### After (Universal)
```python
# Just use user_id
event = {
    "user_id": person.user_id,  # Works for ANY user
    ...
}
```

## Constraints

### MUST FOLLOW

1. ❌ NO user names in CV engine
2. ❌ NO identity-specific logic
3. ❌ NO hardcoded user IDs
4. ✅ USE user_id (nullable)
5. ✅ USE track IDs
6. ✅ Backend resolves names

### GUARANTEED

- Works for existing 39 users
- Works for future users (auto)
- Works for Unknown users
- No code changes needed per user

## Performance

- **Memory**: O(n) tracks in frame
- **CPU**: O(n×m) ownership checks per frame
  - n = person tracks
  - m = object tracks
- **Typical**: ~10 persons, ~5 objects = 50 ops/frame
- **60 FPS**: Negligible overhead

## Troubleshooting

### "Event not generated"
Check logs for:
```
[TRACK] object_track=X
[OWNERSHIP] ...
[DROP] ...
[EVENT] ...
```

If missing ownership, check:
- Distance threshold
- Duration threshold

### "Duplicate events"
Should never happen due to:
- `event_generated` flag
- Single call per track

### "Unknown user_id"
Expected behavior. Backend handles:
```python
user_name = "Unknown" if not user_id else resolve(user_id)
```

## Summary

This system is **100% generic** and **automatically works for all users**:

- ✅ Face recognition assigns user_id (or None)
- ✅ Ownership tracks by user_id
- ✅ Events include user_id
- ✅ Backend resolves user_id → name
- ✅ Frontend displays name or "Unknown"

**No code changes needed when adding new users.**
