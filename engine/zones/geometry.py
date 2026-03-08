"""
Geometry utilities for zone polygon intersection testing.

Implements ray-casting algorithm for point-in-polygon detection and
Intersection over Union (IoU) computation for bounding boxes.
"""

from typing import Tuple, List


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    Determine if a point is inside a polygon using the ray-casting algorithm.

    The algorithm casts a ray from the point to infinity (typically along the
    positive x-axis) and counts how many edges of the polygon it crosses. If the
    count is odd, the point is inside; if even, the point is outside.

    Args:
        point: A tuple (x, y) representing the test point in pixel coordinates.
        polygon: A list of tuples [(x1, y1), (x2, y2), ...] representing the
                 vertices of the polygon in order. The polygon is assumed to be
                 closed (first and last vertices are connected).

    Returns:
        True if the point is inside the polygon (including on the boundary for
        certain edge cases), False otherwise.
        Returns False if the polygon has fewer than 3 vertices (degenerate polygon).

    Note:
        For bounding box intersection with zones, use the bottom-center of the
        bounding box as the test point: (x1 + (x2 - x1) / 2, y2) represents
        feet-on-ground, which is more accurate than the centroid.
    """
    # Handle degenerate polygons
    if len(polygon) < 3:
        return False

    x, y = point
    inside = False

    # Iterate through each edge of the polygon
    n = len(polygon)
    p1x, p1y = polygon[0]

    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]

        # Check if the ray crosses this edge
        # The ray goes from (x, y) to (infinity, y)

        # Edge is horizontal: skip
        if p1y == p2y:
            p1x, p1y = p2x, p2y
            continue

        # Ensure p1y < p2y for consistent comparison
        if p1y > p2y:
            p1x, p1y, p2x, p2y = p2x, p2y, p1x, p1y

        # Check if the ray's y-coordinate is within the edge's y-range
        if y < p1y or y >= p2y:
            p1x, p1y = p2x, p2y
            continue

        # Compute the x-coordinate of the intersection of the ray with the edge
        # Use the line equation: x_intersect = p1x + (y - p1y) * (p2x - p1x) / (p2y - p1y)
        x_intersect = p1x + (y - p1y) * (p2x - p1x) / (p2y - p1y)

        # If the intersection is to the right of the test point, toggle inside
        if x < x_intersect:
            inside = not inside

        p1x, p1y = p2x, p2y

    return inside


def compute_iou(box1: Tuple[float, float, float, float], box2: Tuple[float, float, float, float]) -> float:
    """
    Compute the Intersection over Union (IoU) of two bounding boxes.

    IoU is a measure of overlap between two boxes, commonly used in object detection.
    It is calculated as: IoU = intersection_area / union_area

    Args:
        box1: A tuple (x1, y1, x2, y2) representing the first bounding box,
              where (x1, y1) is the top-left corner and (x2, y2) is the
              bottom-right corner.
        box2: A tuple (x1, y1, x2, y2) representing the second bounding box
              in the same format as box1.

    Returns:
        A float in the range [0.0, 1.0] representing the IoU of the two boxes.
        Returns 0.0 if either box has zero area (degenerate box).

    Note:
        Boxes are expected to have x1 < x2 and y1 < y2. If this is not the case,
        the function will still work but may give unexpected results.
    """
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2

    # Compute areas of the two boxes
    area1 = (x1_max - x1_min) * (y1_max - y1_min)
    area2 = (x2_max - x2_min) * (y2_max - y2_min)

    # If either box has zero area, return 0.0
    if area1 <= 0.0 or area2 <= 0.0:
        return 0.0

    # Compute the intersection
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)

    # Check if there is an intersection
    if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
        intersection_area = 0.0
    else:
        intersection_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)

    # Compute the union
    union_area = area1 + area2 - intersection_area

    # Avoid division by zero (should not happen if area checks are correct)
    if union_area <= 0.0:
        return 0.0

    # Compute IoU
    iou = intersection_area / union_area

    return iou
