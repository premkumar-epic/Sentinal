from __future__ import annotations

from typing import Iterable, List, Tuple

import cv2
import numpy as np

from Core_AI.utils.geometry import bbox_bottom_center, point_in_polygon
from Core_AI.zones import Zone, ZoneManager


Color = Tuple[int, int, int]

# Pre-compute zone overlay color constant
_ZONE_COLOR: Color = (0, 255, 255)
_INTRUDER_COLOR: Color = (0, 0, 255)
_FOOT_DOT_COLOR: Color = (0, 255, 0)


def _track_color(track_id: int) -> Color:
    return (int(track_id * 37) % 255, int(track_id * 17) % 255, int(track_id * 53) % 255)


def draw_overlays(frame: np.ndarray, tracks: Iterable[dict], zone_manager: ZoneManager, fps: float = 0.0) -> np.ndarray:
    """Draw bounding boxes, track IDs, and zones onto the frame."""
    if fps > 0:
        text = f"FPS: {fps:.1f}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2
        (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
        cv2.rectangle(frame, (10, 10), (20 + tw, 20 + th + 5), (0, 0, 0), -1)
        cv2.putText(frame, text, (15, 20 + th), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    zones: List[Zone] = getattr(zone_manager, "_zones", [])

    for track in tracks:
        if "bbox" not in track or "track_id" not in track:
            continue
        x1, y1, x2, y2 = (int(v) for v in track["bbox"])
        track_id = int(track.get("stable_id", track["track_id"]))

        # Compute foot point once
        nx, ny = bbox_bottom_center(track["bbox"])
        nx, ny = int(nx), int(ny)

        # Compute zone membership once (not per-zone check repeated in loop)
        is_in_zone = any(point_in_polygon((nx, ny), z.polygon) for z in zones)

        score = track.get("reid_score", 1.0)
        color = _INTRUDER_COLOR if is_in_zone else _track_color(track_id)
        
        display_name = track.get("name", f"ID {track_id}")
        label = f"{display_name} ({score:.2f})" + (" [!]" if is_in_zone else "")

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (nx, ny), radius=4, color=_FOOT_DOT_COLOR, thickness=-1)
        cv2.putText(frame, label, (x1, max(0, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

    for zone in zones:
        _draw_zone(frame, zone)

    return frame


def _draw_zone(frame: np.ndarray, zone: Zone) -> None:
    pts = np.array(zone.polygon, dtype=np.int32)
    cv2.polylines(frame, [pts], isClosed=True, color=_ZONE_COLOR, thickness=2)
    if len(zone.polygon) > 0:
        x, y = zone.polygon[0]
        cv2.putText(frame, zone.label, (int(x), int(y) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _ZONE_COLOR, 2, cv2.LINE_AA)
