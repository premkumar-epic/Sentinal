"""
SENTINAL v2 — Anomaly Detection
Identifies behavioral patterns (loitering, crowding, violence) from tracks and zone events.
Uses kinematic analysis (velocity, proximity, aspect ratio) for robust detection.
"""

import time
import math
import threading
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Optional

from engine.config import settings
from engine.vision.tracker import Track
from engine.zones.manager import ZoneIntrusion
from engine.zones.geometry import compute_iou


@dataclass
class Anomaly:
    """Represents a detected behavioral anomaly."""
    type: str          # 'loitering' | 'crowding' | 'violence'
    zone_id: str
    track_ids: List[int]
    detail: str        # human-readable description


class AnomalyDetector:
    """
    Detects behavioral anomalies in real-time.

    This module tracks state across frames to identify patterns like 
    loitering, crowd formation, and physical altercations.
    """

    def __init__(self) -> None:
        """Initialize detector with empty state and thread safety lock."""
        self._lock = threading.RLock()

        # State for loitering: track_id -> {zone_id: first_seen_timestamp}
        self._loiter_state: Dict[int, Dict[str, float]] = {}

        # State for crowding: zone_id -> last_fire_timestamp
        self._crowd_last_fired: Dict[str, float] = {}

        # Kinematic state: track_id -> (last_bbox, last_timestamp)
        self._history: Dict[int, Tuple[Tuple[int, int, int, int], float]] = {}

        # Pair interaction state: (min_tid, max_tid) -> {first_seen, last_fired, peak_intensity}
        self._interaction_state: Dict[Tuple[int, int], Dict] = {}

    def update(self, tracks: List[Track], zone_events: List[ZoneIntrusion]) -> List[Anomaly]:
        """
        Process current frame data to detect anomalies.

        Args:
            tracks: List of active Track objects in the current frame.
            zone_events: List of ZoneIntrusion objects (tracks currently in zones).

        Returns:
            List of detected Anomaly objects.
        """
        anomalies: List[Anomaly] = []
        now = time.time()

        with self._lock:
            # 1. Update kinematic history and build active sets
            active_track_ids = {t.track_id for t in tracks}
            self._update_history(tracks, now)

            active_intrusions: Set[Tuple[int, str]] = {(z.track_id, z.zone_id) for z in zone_events}

            # 2. Process Loitering
            anomalies.extend(self._check_loitering(active_intrusions, now))

            # 3. Process Crowding
            anomalies.extend(self._check_crowding(zone_events, now))

            # 4. Process Violence (Advanced)
            anomalies.extend(self._check_violence_kinematic(tracks, active_track_ids, now))

            # 5. Cleanup stale history
            self._cleanup_history(active_track_ids)

        return anomalies

    def _update_history(self, tracks: List[Track], now: float) -> None:
        """Store bounding box history for velocity calculation."""
        for t in tracks:
            self._history[t.track_id] = (t.bbox, now)

    def _cleanup_history(self, active_track_ids: Set[int]) -> None:
        """Remove tracks that are no longer in frame."""
        for tid in list(self._history.keys()):
            if tid not in active_track_ids:
                del self._history[tid]
        
        for pair in list(self._interaction_state.keys()):
            if pair[0] not in active_track_ids or pair[1] not in active_track_ids:
                del self._interaction_state[pair]

    def _check_loitering(self, active_intrusions: Set[Tuple[int, str]], now: float) -> List[Anomaly]:
        """Check for tracks staying in the same zone beyond the threshold."""
        found: List[Anomaly] = []

        # Clean up tracks that are no longer active in their previous zones
        for tid in list(self._loiter_state.keys()):
            active_zones_for_track = {zid for (t, zid) in active_intrusions if t == tid}
            for zid in list(self._loiter_state[tid].keys()):
                if zid not in active_zones_for_track:
                    del self._loiter_state[tid][zid]
            if not self._loiter_state[tid]:
                del self._loiter_state[tid]

        # Update and check thresholds
        for tid, zid in active_intrusions:
            if tid not in self._loiter_state:
                self._loiter_state[tid] = {}
            if zid not in self._loiter_state[tid]:
                self._loiter_state[tid][zid] = now
            else:
                duration = now - self._loiter_state[tid][zid]
                if duration > settings.loitering_seconds:
                    found.append(Anomaly(
                        type='loitering',
                        zone_id=zid,
                        track_ids=[tid],
                        detail=f"Person #{tid} loitering in zone {zid} for {int(duration)}s"
                    ))
                    del self._loiter_state[tid][zid]

        return found

    def _check_crowding(self, zone_events: List[ZoneIntrusion], now: float) -> List[Anomaly]:
        """Check for zones exceeding the person count threshold."""
        found: List[Anomaly] = []
        counts: Dict[str, List[int]] = {}
        for z in zone_events:
            if z.zone_id not in counts:
                counts[z.zone_id] = []
            counts[z.zone_id].append(z.track_id)

        for zid, track_ids in counts.items():
            if len(track_ids) > settings.crowd_threshold:
                last_fired = self._crowd_last_fired.get(zid, 0)
                if now - last_fired > settings.alert_cooldown_seconds:
                    found.append(Anomaly(
                        type='crowding',
                        zone_id=zid,
                        track_ids=track_ids,
                        detail=f"Crowd of {len(track_ids)} persons detected in zone {zid}"
                    ))
                    self._crowd_last_fired[zid] = now
        return found

    def _check_violence_kinematic(self, tracks: List[Track], active_track_ids: Set[int], now: float) -> List[Anomaly]:
        """
        Advanced violence detection using Kinematics:
        - Proximity (Normalized distance)
        - Velocity (Movement magnitude)
        - BBox Overlap (Physical contact)
        """
        found: List[Anomaly] = []
        num_tracks = len(tracks)
        
        # We need a small helper to get centers
        def get_center(bbox):
            return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

        for i in range(num_tracks):
            for j in range(i + 1, num_tracks):
                t1, t2 = tracks[i], tracks[j]
                
                # 1. Proximity Check
                c1, c2 = get_center(t1.bbox), get_center(t2.bbox)
                dist = math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)
                
                h1 = t1.bbox[3] - t1.bbox[1]
                h2 = t2.bbox[3] - t2.bbox[1]
                avg_height = (h1 + h2) / 2
                
                if avg_height == 0: continue
                normalized_dist = dist / avg_height
                
                # 2. Velocity / Intensity Check
                # Combined normalized movement of both tracks
                # (magnitude / height)
                v1 = self._get_normalized_velocity(t1.track_id, t1.bbox, now)
                v2 = self._get_normalized_velocity(t2.track_id, t2.bbox, now)
                intensity = v1 + v2
                
                # 3. Contact check (IoU)
                iou = compute_iou(t1.bbox, t2.bbox)
                
                # Logic: They are close OR overlapping, and moving fast
                is_proximal = normalized_dist < settings.violence_proximity_threshold
                is_touching = iou > 0.15
                is_rapid = intensity > settings.violence_velocity_threshold
                
                pair = (min(t1.track_id, t2.track_id), max(t1.track_id, t2.track_id))
                
                if (is_proximal or is_touching) and is_rapid:
                    if pair not in self._interaction_state:
                        self._interaction_state[pair] = {
                            'first_seen': now,
                            'last_fired': 0,
                            'peak_intensity': intensity
                        }
                    
                    state = self._interaction_state[pair]
                    state['peak_intensity'] = max(state['peak_intensity'], intensity)
                    duration = now - state['first_seen']
                    
                    # Fire if intensity persists for a bit or is extremely high
                    if duration > 1.5 and (now - state['last_fired'] > settings.violence_cooldown_seconds):
                        found.append(Anomaly(
                            type='violence',
                            zone_id='none',
                            track_ids=list(pair),
                            detail=f"Physical altercation detected between #{pair[0]} and #{pair[1]} (intensity={state['peak_intensity']:.2f})"
                        ))
                        state['last_fired'] = now
                else:
                    # Decay interaction state if they calm down or separate
                    if pair in self._interaction_state:
                        # If separated for more than 2 seconds, remove
                        if now - self._interaction_state[pair]['first_seen'] > 2.0:
                            del self._interaction_state[pair]

        return found

    def _get_normalized_velocity(self, tid: int, current_bbox: Tuple[int, int, int, int], now: float) -> float:
        """Calculate movement magnitude normalized by height per second."""
        if tid not in self._history:
            return 0.0
        
        last_bbox, last_time = self._history[tid]
        dt = now - last_time
        if dt <= 0: return 0.0
        
        # Center movement
        c1 = ((last_bbox[0] + last_bbox[2]) / 2, (last_bbox[1] + last_bbox[3]) / 2)
        c2 = ((current_bbox[0] + current_bbox[2]) / 2, (current_bbox[1] + current_bbox[3]) / 2)
        
        dist = math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)
        height = current_bbox[3] - current_bbox[1]
        
        if height == 0: return 0.0
        
        # normalized distance moved / seconds
        return (dist / height) / dt
