from __future__ import annotations

from typing import Iterable, Tuple


Point = Tuple[float, float]
BBox = Tuple[float, float, float, float]


def bbox_center(bbox: BBox) -> Point:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def bbox_bottom_center(bbox: BBox) -> Point:
    """Return the (x, y) coordinate representing the bottom-center of the bounding box.
    This corresponds to the ground-contact point which is much better for zone tracking.
    """
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, float(y2)


def point_in_polygon(point: Point, polygon: Iterable[Point]) -> bool:
    """Ray casting point-in-polygon algorithm."""
    x, y = point
    poly = list(polygon)
    n = len(poly)
    if n < 3:
        return False

    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        if intersects:
            inside = not inside
        j = i
    return inside

