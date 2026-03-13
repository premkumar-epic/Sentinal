"""
SENTINAL v2 — Re-ID Cross-Camera Diagnostic
Grabs one frame from each running camera, extracts person crops,
computes ReID embeddings, and prints a pairwise similarity matrix.

Usage:
    python tests/diag_reid.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import json
from pathlib import Path

from engine.config import settings
from engine.vision.detector import Detector
from engine.vision.reid import ReIDEngine


def grab_frame(url: str, retries: int = 3):
    """Grab a single frame from a camera URL."""
    for _ in range(retries):
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            continue
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # Drain buffer
        for _ in range(5):
            cap.grab()
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            return frame
    return None


def get_best_person_crop(frame, detector):
    """Detect persons and return the largest crop."""
    detections = detector.detect(frame)
    persons = [d for d in detections if d.class_id == 0]
    if not persons:
        return None, None

    # Pick largest bounding box
    best = max(persons, key=lambda d: (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]))
    h, w = frame.shape[:2]
    x1 = max(0, best.bbox[0])
    y1 = max(0, best.bbox[1])
    x2 = min(w, best.bbox[2])
    y2 = min(h, best.bbox[3])
    crop = frame[y1:y2, x1:x2]
    return crop, best


def main():
    # Load camera list
    cameras_json = Path("data/cameras.json")
    if not cameras_json.exists():
        print("ERROR: data/cameras.json not found. Add cameras via the dashboard first.")
        return

    cameras = json.loads(cameras_json.read_text())
    if not cameras:
        print("ERROR: No cameras in data/cameras.json")
        return

    print(f"Found {len(cameras)} cameras")
    print("=" * 60)

    # Init models
    print("Loading YOLO detector...")
    detector = Detector()

    print("Loading ReID engine...")
    model_path = os.path.join(settings.models_dir, settings.reid_model)
    reid = ReIDEngine(model_path=model_path)
    print(f"  MATCH_THRESHOLD = {reid.MATCH_THRESHOLD}")
    print(f"  MARGIN_THRESHOLD = {reid.MARGIN_THRESHOLD}")
    print(f"  Model type: {reid._model_type}")
    print()

    # Grab frames and extract embeddings
    embeddings = {}
    crops = {}

    for cam in cameras:
        cam_id = cam["cam_id"]
        url = cam["url"]
        print(f"[{cam_id}] Grabbing frame from {url}...")

        frame = grab_frame(url)
        if frame is None:
            print(f"  FAILED to grab frame")
            continue

        print(f"  Frame: {frame.shape[1]}x{frame.shape[0]}")

        crop, det = get_best_person_crop(frame, detector)
        if crop is None:
            print(f"  No person detected")
            continue

        ch, cw = crop.shape[:2]
        print(f"  Person crop: {cw}x{ch} (conf={det.confidence:.2f})")

        emb, quality = reid.extract_embedding(crop)
        norm = np.linalg.norm(emb)
        print(f"  Embedding norm={norm:.4f}, quality={quality:.3f}")

        if norm < 1e-6:
            print(f"  WARNING: zero embedding (crop too small?)")
            continue

        embeddings[cam_id] = emb
        crops[cam_id] = crop

        # Save crop for inspection
        debug_dir = Path("data/debug_reid")
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / f"{cam_id}_crop.jpg"), crop)

    print()
    print("=" * 60)
    print("PAIRWISE COSINE SIMILARITY MATRIX")
    print("=" * 60)

    cam_ids = list(embeddings.keys())
    if len(cam_ids) < 2:
        print("Need at least 2 cameras with detected persons")
        return

    # Header
    print(f"{'':>12}", end="")
    for cid in cam_ids:
        print(f"{cid:>12}", end="")
    print()

    # Matrix
    for i, cid_a in enumerate(cam_ids):
        print(f"{cid_a:>12}", end="")
        for j, cid_b in enumerate(cam_ids):
            sim = float(np.dot(embeddings[cid_a], embeddings[cid_b]))
            marker = ""
            if i != j:
                if sim >= reid.MATCH_THRESHOLD:
                    marker = " OK"
                else:
                    marker = " !!"
            print(f"{sim:>9.4f}{marker}", end="")
        print()

    print()
    print(f"Threshold: {reid.MATCH_THRESHOLD}")
    print(f"OK = would match, !! = would NOT match (below threshold)")
    print()

    # Recommendations
    all_sims = []
    for i, cid_a in enumerate(cam_ids):
        for j, cid_b in enumerate(cam_ids):
            if i < j:
                sim = float(np.dot(embeddings[cid_a], embeddings[cid_b]))
                all_sims.append((cid_a, cid_b, sim))

    if all_sims:
        min_pair = min(all_sims, key=lambda x: x[2])
        max_pair = max(all_sims, key=lambda x: x[2])
        avg_sim = np.mean([s[2] for s in all_sims])

        print(f"Best pair:  {max_pair[0]} <-> {max_pair[1]} = {max_pair[2]:.4f}")
        print(f"Worst pair: {min_pair[0]} <-> {min_pair[1]} = {min_pair[2]:.4f}")
        print(f"Average:    {avg_sim:.4f}")
        print()

        if min_pair[2] < reid.MATCH_THRESHOLD:
            suggested = max(0.20, min_pair[2] - 0.05)
            print(f"RECOMMENDATION: Lower REID_THRESHOLD to {suggested:.2f} in .env")
            print(f"  Current: {reid.MATCH_THRESHOLD}")
            print(f"  Worst cross-cam similarity: {min_pair[2]:.4f}")

    print()
    print(f"Debug crops saved to data/debug_reid/")


if __name__ == "__main__":
    main()
