"""
SENTINAL v2 — Anomaly Detection
Identifies behavioral patterns (loitering, crowding, violence) from tracks and zone events.
"""

import time
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

    This module tracks state across frames to identify time-based patterns
    like loitering, crowd formation, and physical altercations.
    """

    def __init__(self) -> None:
        """Initialize detector with empty state and thread safety lock."""
        self._lock = threading.RLock()

        # State for loitering: track_id -> {zone_id: first_seen_timestamp}
        self._loiter_state: Dict[int, Dict[str, float]] = {}

        # State for crowding: zone_id -> last_fire_timestamp
        self._crowd_last_fired: Dict[str, float] = {}

        # State for violence: (min_tid, max_tid) -> first_overlap_timestamp
        self._violence_state: Dict[Tuple[int, int], float] = {}

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
            # 1. Build active sets for processing
            active_track_ids = {t.track_id for t in tracks}
            active_intrusions: Set[Tuple[int, str]] = {(z.track_id, z.zone_id) for z in zone_events}

            # 2. Process Loitering
            anomalies.extend(self._check_loitering(active_intrusions, now))

            # 3. Process Crowding
            anomalies.extend(self._check_crowding(zone_events, now))

            # 4. Process Violence
            anomalies.extend(self._check_violence(tracks, active_track_ids, now))

        return anomalies

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
                # First time seeing this track in this zone
                self._loiter_state[tid][zid] = now
            else:
                # Still here, check duration
                duration = now - self._loiter_state[tid][zid]
                if duration > settings.loitering_seconds:
                    found.append(Anomaly(
                        type='loitering',
                        zone_id=zid,
                        track_ids=[tid],
                        detail=f"Person #{tid} loitering in zone {zid} for {int(duration)}s"
                    ))
                    # Fire once: clear this entry to avoid spamming
                    del self._loiter_state[tid][zid]

        return found

    def _check_crowding(self, zone_events: List[ZoneIntrusion], now: float) -> List[Anomaly]:
        """Check for zones exceeding the person count threshold."""
        found: List[Anomaly] = []

        # Count persons per zone
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

    def _check_violence(self, tracks: List[Track], active_track_ids: Set[int], now: float) -> List[Anomaly]:
        """Check for physical altercations based on bbox overlap duration."""
        found: List[Anomaly] = []

        # 1. Clean up stale pairs
        for pair in list(self._violence_state.keys()):
            if pair[0] not in active_track_ids or pair[1] not in active_track_ids:
                del self._violence_state[pair]

        # 2. Check all pairs of tracks
        num_tracks = len(tracks)
        for i in range(num_tracks):
            for j in range(i + 1, num_tracks):
                t1, t2 = tracks[i], tracks[j]

                # Compute IoU
                iou = compute_iou(t1.bbox, t2.bbox)
                pair = (min(t1.track_id, t2.track_id), max(t1.track_id, t2.track_id))

                if iou > 0.40:
                    if pair not in self._violence_state:
                        self._violence_state[pair] = now
                    else:
                        duration = now - self._violence_state[pair]
                        if duration > 3.0:
                            found.append(Anomaly(
                                type='violence',
                                zone_id='none',
                                track_ids=list(pair),
                                detail=f"Potential violence/altercation between #{pair[0]} and #{pair[1]} (overlap > 3s)"
                            ))
                            # Fire once: clear pair after firing
                            del self._violence_state[pair]
                else:
                    # Reset if they separate
                    if pair in self._violence_state:
                        del self._violence_state[pair]

        return found
