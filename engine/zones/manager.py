"""
Zone management system for SENTINAL v2.

Manages detection zones and performs intrusion detection.
Supports hot-reloading of zone configurations via watchdog.
"""

import json
import threading
import logging
import dataclasses
import tempfile
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple, Dict, Any

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

from engine.zones.geometry import point_in_polygon
from engine.config import settings

logger = logging.getLogger(__name__)

@dataclass
class Zone:
    """Represents a virtual detection zone in a camera feed."""
    zone_id: str
    label: str
    cam_id: str
    polygon: List[Tuple[float, float]]
    color: str = '#FF0000'
    active: bool = True

@dataclass
class ZoneIntrusion:
    """Represents an intrusion event within a zone."""
    zone_id: str
    zone_label: str
    cam_id: str
    track_id: int
    global_id: str

class ZoneManager:
    """
    Manages detection zones and performs intrusion detection.

    This class is thread-safe and supports hot-reloading of zone configurations.
    """

    def __init__(self, zones_file: str = settings.zones_file) -> None:
        """
        Initialize the ZoneManager and load zones from the specified file.

        Args:
            zones_file: Path to the JSON file containing zone configurations.
        """
        self.zones_file = zones_file
        self.zones: List[Zone] = []
        self._lock = threading.RLock()

        self.reload()

        if HAS_WATCHDOG:
            try:
                self._setup_watchdog()
            except Exception as e:
                logger.warning(f"Failed to start watchdog for zone file: {e}")
        else:
            logger.warning("Watchdog not available. Hot-reloading of zones will be disabled.")

    def _setup_watchdog(self) -> None:
        """Setup watchdog observer for hot-reloading the zones file."""
        class ZoneFileHandler(FileSystemEventHandler):
            def __init__(self, manager: 'ZoneManager'):
                self.manager = manager

            def on_modified(self, event):
                if event.src_path == os.path.abspath(self.manager.zones_file):
                    logger.info(f"Zones file {self.manager.zones_file} modified. Reloading...")
                    self.manager.reload()

        self.observer = Observer()
        handler = ZoneFileHandler(self)
        watch_dir = os.path.dirname(os.path.abspath(self.zones_file))
        if not os.path.exists(watch_dir):
            os.makedirs(watch_dir, exist_ok=True)

        self.observer.schedule(handler, watch_dir, recursive=False)
        self.observer.start()

    def reload(self) -> None:
        """
        Re-read the zones_file and update the internal zones list.
        Thread-safe operation.
        """
        with self._lock:
            if not os.path.exists(self.zones_file):
                logger.warning(f"Zones file {self.zones_file} does not exist. Initializing empty list.")
                self.zones = []
                return

            try:
                with open(self.zones_file, 'r') as f:
                    data = json.load(f)
                    new_zones = []
                    for item in data:
                        # Convert polygon list of lists to list of tuples if necessary
                        if 'polygon' in item:
                            item['polygon'] = [tuple(p) for p in item['polygon']]
                        new_zones.append(Zone(**item))
                    self.zones = new_zones
                    logger.debug(f"Successfully reloaded {len(self.zones)} zones.")
            except Exception as e:
                logger.error(f"Error loading zones file {self.zones_file}: {e}")

    def _save_atomic(self) -> None:
        """Atomically write the current zones list to the zones_file."""
        with self._lock:
            data = [asdict(z) for z in self.zones]
            temp_dir = os.path.dirname(os.path.abspath(self.zones_file))
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir, exist_ok=True)

            temp_fd, temp_path = tempfile.mkstemp(
                dir=temp_dir,
                prefix="zones_tmp_"
            )
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(data, f, indent=4)
                # Atomic rename
                os.replace(temp_path, self.zones_file)
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                logger.error(f"Failed to save zones atomically: {e}")
                raise

    def check_intrusions(self, tracks: List[Any], cam_id: str) -> List[ZoneIntrusion]:
        """
        Check if any tracks are intruding into active zones for a given camera.

        Uses the bottom-center of the track's bounding box as the test point.

        Args:
            tracks: List of objects with .track_id (int) and .bbox (tuple: x1, y1, x2, y2).
            cam_id: The ID of the camera to check zones for.

        Returns:
            A list of ZoneIntrusion objects.
        """
        intrusions = []
        with self._lock:
            active_cam_zones = [z for z in self.zones if z.cam_id == cam_id and z.active]

            if not active_cam_zones:
                return []

            for track in tracks:
                x1, y1, x2, y2 = track.bbox
                # Bottom-center point (feet-on-ground)
                point = (x1 + (x2 - x1) / 2.0, y2)

                for zone in active_cam_zones:
                    if point_in_polygon(point, zone.polygon):
                        intrusions.append(ZoneIntrusion(
                            zone_id=zone.zone_id,
                            zone_label=zone.label,
                            cam_id=cam_id,
                            track_id=track.track_id,
                            global_id=getattr(track, 'global_id', f"{cam_id}:{track.track_id}")
                        ))
        return intrusions

    def get_zones_for_camera(self, cam_id: str) -> List[Zone]:
        """
        Return all zones associated with a specific camera ID.

        Args:
            cam_id: The camera ID to filter by.

        Returns:
            A list of Zone objects.
        """
        with self._lock:
            return [z for z in self.zones if z.cam_id == cam_id]

    def add_zone(self, zone: Zone) -> None:
        """
        Add a new zone and persist it to the zones file.

        Args:
            zone: The Zone object to add.
        """
        with self._lock:
            # Check if zone_id already exists and remove it to replace
            self.zones = [z for z in self.zones if z.zone_id != zone.zone_id]
            self.zones.append(zone)
            self._save_atomic()
            logger.info(f"Zone added: {zone.zone_id} ({zone.label})")

    def remove_zone(self, zone_id: str) -> None:
        """
        Remove a zone by its ID and update the zones file.

        Args:
            zone_id: The unique ID of the zone to remove.
        """
        with self._lock:
            original_count = len(self.zones)
            self.zones = [z for z in self.zones if z.zone_id != zone_id]
            if len(self.zones) < original_count:
                self._save_atomic()
                logger.info(f"Zone removed: {zone_id}")
            else:
                logger.warning(f"Attempted to remove non-existent zone: {zone_id}")
