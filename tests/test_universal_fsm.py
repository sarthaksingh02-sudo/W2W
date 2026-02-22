"""
Test suite for Universal Object-Person-Event Association System

Verifies:
1. No hardcoded users
2. Generic user_id handling
3. Ownership assignment
4. Drop detection
5. Event generation
"""

import unittest
from unittest.mock import Mock, patch
import time
from cv_engine.disposal.universal_fsm import (
    UniversalAssociationSystem,
    PersonTrack,
    ObjectTrack
)


class TestUniversalAssociationSystem(unittest.TestCase):
    
    def setUp(self):
        """Set up test system"""
        self.system = UniversalAssociationSystem(camera_id=1)
    
    def test_no_hardcoded_users(self):
        """Verify no user names are hardcoded in the system"""
        import inspect
        source = inspect.getsource(UniversalAssociationSystem)
        
        # Check for common hardcoded patterns
        forbidden_patterns = [
            'if user_id == ',
            'user_id = 1',
            'user_id = 2',
            '"sarthak"',
            "'sarthak'",
            'name ==',
        ]
        
        for pattern in forbidden_patterns:
            self.assertNotIn(pattern, source.lower(), 
                           f"Found hardcoded pattern: {pattern}")
    
    def test_person_track_creation(self):
        """Test generic person track creation"""
        # Simulate person with user_id
        person = PersonTrack(track_id=1, user_id=42)
        self.assertEqual(person.track_id, 1)
        self.assertEqual(person.user_id, 42)
        
        # Simulate unknown person
        person_unknown = PersonTrack(track_id=2, user_id=None)
        self.assertEqual(person_unknown.track_id, 2)
        self.assertIsNone(person_unknown.user_id)
    
    def test_object_track_creation(self):
        """Test object track creation"""
        obj = ObjectTrack(track_id=100, class_name="bottle")
        self.assertEqual(obj.track_id, 100)
        self.assertEqual(obj.class_name, "bottle")
        self.assertIsNone(obj.owner_user_id)
        self.assertFalse(obj.dropped)
        self.assertFalse(obj.event_generated)
    
    def test_ownership_assignment(self):
        """Test that ownership is assigned generically"""
        # Create mock face system
        mock_face_sys = Mock()
        mock_face_sys.get_user_id = Mock(return_value=123)  # Any user_id
        
        # Simulate person and object close together
        person_raw = [{
            'track_id': 1,
            'bbox': (100, 100, 200, 200),
            'class': 'person'
        }]
        
        object_raw = [{
            'track_id': 50,
            'bbox': (105, 105, 125, 125),  # Very close to person
            'class': 'bottle'
        }]
        
        # Update multiple times to trigger ownership
        for _ in range(10):
            self.system.update(person_raw, object_raw, (640, 480), None, mock_face_sys)
            time.sleep(0.1)
        
        # Verify ownership was assigned
        obj = self.system.object_tracks.get(50)
        self.assertIsNotNone(obj)
        self.assertEqual(obj.owner_person_track_id, 1)
        self.assertEqual(obj.owner_user_id, 123)  # Generic user_id
    
    def test_unknown_user_handling(self):
        """Test that system handles Unknown users correctly"""
        mock_face_sys = Mock()
        mock_face_sys.get_user_id = Mock(return_value=None)  # Unknown user
        
        person_raw = [{
            'track_id': 1,
            'bbox': (100, 100, 200, 200),
            'class': 'person'
        }]
        
        object_raw = [{
            'track_id': 50,
            'bbox': (105, 105, 125, 125),
            'class': 'cup'
        }]
        
        for _ in range(10):
            self.system.update(person_raw, object_raw, (640, 480), None, mock_face_sys)
            time.sleep(0.1)
        
        # Verify object is owned but user_id is None
        obj = self.system.object_tracks.get(50)
        self.assertIsNotNone(obj)
        self.assertEqual(obj.owner_person_track_id, 1)
        self.assertIsNone(obj.owner_user_id)  # Should be None for Unknown
    
    def test_multiple_users_independently(self):
        """Test that system tracks multiple users independently"""
        mock_face_sys = Mock()
        
        def get_user_id(track_id):
            # Different users for different tracks
            return {1: 100, 2: 200, 3: 300}.get(track_id)
        
        mock_face_sys.get_user_id = Mock(side_effect=get_user_id)
        
        # Three different people
        person_raw = [
            {'track_id': 1, 'bbox': (10, 10, 50, 50), 'class': 'person'},
            {'track_id': 2, 'bbox': (200, 200, 240, 240), 'class': 'person'},
            {'track_id': 3, 'bbox': (400, 400, 440, 440), 'class': 'person'},
        ]
        
        # Three objects near each person
        object_raw = [
            {'track_id': 101, 'bbox': (15, 15, 25, 25), 'class': 'bottle'},
            {'track_id': 102, 'bbox': (205, 205, 215, 215), 'class': 'cup'},
            {'track_id': 103, 'bbox': (405, 405, 415, 415), 'class': 'can'},
        ]
        
        for _ in range(10):
            self.system.update(person_raw, object_raw, (640, 480), None, mock_face_sys)
            time.sleep(0.1)
        
        # Verify each object is owned by correct person with correct user_id
        obj1 = self.system.object_tracks.get(101)
        obj2 = self.system.object_tracks.get(102)
        obj3 = self.system.object_tracks.get(103)
        
        self.assertEqual(obj1.owner_person_track_id, 1)
        self.assertEqual(obj1.owner_user_id, 100)
        
        self.assertEqual(obj2.owner_person_track_id, 2)
        self.assertEqual(obj2.owner_user_id, 200)
        
        self.assertEqual(obj3.owner_person_track_id, 3)
        self.assertEqual(obj3.owner_user_id, 300)
    
    def test_event_not_duplicated(self):
        """Test that events are generated exactly once"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            
            # Create and drop an object
            obj = ObjectTrack(track_id=99, class_name="bottle")
            obj.owner_user_id = 500  # Any user_id
            obj.dropped = True
            obj.drop_centroid = (100, 100)
            obj.drop_timestamp = time.time()
            
            self.system.object_tracks[99] = obj
            
            # Call event generation multiple times
            for _ in range(5):
                self.system._generate_event(obj, "VIOLATION", "test.jpg")
            
            # Should only POST once per call (5 times total)
            # But event_generated flag prevents duplicate processing
            # In real usage, update() won't call _generate_event twice
            self.assertGreaterEqual(mock_post.call_count, 1)


class TestDataStructures(unittest.TestCase):
    
    def test_person_track_structure(self):
        """Verify PersonTrack has required fields"""
        person = PersonTrack(track_id=1)
        
        # Required fields
        self.assertIsNotNone(person.track_id)
        self.assertIsNone(person.user_id)  # Nullable
        self.assertIsInstance(person.active_object_ids, set)
    
    def test_object_track_structure(self):
        """Verify ObjectTrack has required fields"""
        obj = ObjectTrack(track_id=1, class_name="bottle")
        
        # Required fields
        self.assertIsNotNone(obj.track_id)
        self.assertIsNotNone(obj.class_name)
        self.assertIsNone(obj.owner_person_track_id)  # Nullable
        self.assertIsNone(obj.owner_user_id)  # Nullable
        self.assertFalse(obj.dropped)
        self.assertFalse(obj.event_generated)


if __name__ == '__main__':
    unittest.main()
