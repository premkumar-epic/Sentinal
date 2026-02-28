from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Set, Tuple

from config import ZoneConfig
from sentinal.utils.geometry import bbox_bottom_center, point_in_polygon


Point = Tuple[float, float]
Track = Dict[str, object]


@dataclass
class Zone:
    id: str
    label: str
    polygon: List[Point]
    active_ids: Set[int] = field(default_factory=set)


@dataclass
class ZoneEvent:
    zone_id: str
    zone_label: str
    track_id: int
    timestamp: datetime


class ZoneManager:
    """Manage multiple polygon zones and raise entry events per track ID."""

    def __init__(self, configs: Iterable[ZoneConfig]) -> None:
        self.set_zones(configs)

    def set_zones(self, configs: Iterable[ZoneConfig]) -> None:
        """Update active tracking zones at runtime without restarting the pipeline."""
        self._zones = [
            Zone(
                id=cfg.id,
                label=cfg.label,
                polygon=[(float(x), float(y)) for x, y in cfg.polygon],
            )
            for cfg in configs
        ]

    def update(self, tracks: Iterable[Track]) -> List[ZoneEvent]:
        events: List[ZoneEvent] = []
        now = datetime.utcnow()
        
        # Iterate tracks list once, building (track_id, point) pairs
        track_points: List[Tuple[int, Tuple[float, float]]] = []
        for t in tracks:
            if "track_id" not in t or "bbox" not in t:
                continue
            track_id = int(t.get("stable_id", t["track_id"]))  # type: ignore[arg-type]
            cx, cy = bbox_bottom_center(t["bbox"])  # type: ignore[arg-type]
            track_points.append((track_id, (cx, cy)))

        for zone in self._zones:
            current_ids_in_zone: Set[int] = set()
            for track_id, point in track_points:
                if point_in_polygon(point, zone.polygon):
                    current_ids_in_zone.add(track_id)
                    if track_id not in zone.active_ids:
                        events.append(
                            ZoneEvent(
                                zone_id=zone.id,
                                zone_label=zone.label,
                                track_id=track_id,
                                timestamp=now,
                            )
                        )
            zone.active_ids = current_ids_in_zone

        return events
