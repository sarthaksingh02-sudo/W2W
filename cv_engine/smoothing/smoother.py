import numpy as np

class TrackSmoother:
    def __init__(self):
        self.tracks = {} # id -> {'history': [], 'velocity': (0,0)}

    def update(self, tracks):
        """
        Update smoothed trajectories and calculate velocity.
        """
        current_ids = []
        for t in tracks:
            tracker_id = t["track_id"]
            if tracker_id is None: continue
            current_ids.append(tracker_id)
            
            xyxy = t["bbox"]
            curr_pos = np.array(t["centroid"])

            if tracker_id not in self.tracks:
                self.tracks[tracker_id] = {
                    'pos': curr_pos,
                    'velocity': np.array([0.0, 0.0]),
                    'history': [curr_pos]
                }
            else:
                # EMA Smoothing
                alpha = 0.6
                prev_pos = self.tracks[tracker_id]['pos']
                new_pos = alpha * curr_pos + (1 - alpha) * prev_pos
                
                velocity = new_pos - prev_pos
                
                self.tracks[tracker_id]['pos'] = new_pos
                self.tracks[tracker_id]['velocity'] = velocity
                self.tracks[tracker_id]['history'].append(new_pos)
                
                if len(self.tracks[tracker_id]['history']) > 100:
                    self.tracks[tracker_id]['history'].pop(0)

        # Cleanup
        for tid in list(self.tracks.keys()):
            if tid not in current_ids:
                del self.tracks[tid]

    def get_state(self, tracker_id):
        return self.tracks.get(tracker_id, None)
