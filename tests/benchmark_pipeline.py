"""
SENTINAL v2 — Pipeline Benchmark
Profiles each stage of the AI pipeline with real snapshots + synthetic frames.
Run: python -m tests.benchmark_pipeline
"""

import time
import statistics
import cv2
import numpy as np
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_test_frames() -> list[np.ndarray]:
    """Load real snapshots + generate synthetic frames with fake people."""
    frames = []

    # 1. Load real snapshots from data/snapshots/
    snap_dirs = ["data/snapshots/2026-03-09", "data/snapshots/identities"]
    for d in snap_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".jpg"):
                    img = cv2.imread(os.path.join(d, f))
                    if img is not None:
                        frames.append(img)

    # 2. Generate synthetic 720p frames with rectangles (YOLO won't detect these
    #    as people, but it tests raw throughput)
    for _ in range(5):
        frame = np.random.randint(50, 200, (720, 1280, 3), dtype=np.uint8)
        # Draw some rectangle shapes to give YOLO something to process
        cv2.rectangle(frame, (200, 100), (400, 500), (0, 255, 0), -1)
        cv2.rectangle(frame, (600, 150), (800, 550), (255, 0, 0), -1)
        frames.append(frame)

    print(f"Loaded {len(frames)} test frames ({len(frames)-5} real snapshots + 5 synthetic)")
    for i, f in enumerate(frames):
        print(f"  Frame {i}: {f.shape[1]}x{f.shape[0]}")
    return frames


def benchmark_detector(frames: list[np.ndarray], n_warmup: int = 3, n_runs: int = 20):
    """Benchmark YOLO detection."""
    from engine.vision.detector import Detector
    print("\n" + "="*60)
    print("BENCHMARK: Detector (YOLO11l)")
    print("="*60)

    detector = Detector()

    # Warmup (first few runs are slow due to CUDA kernel compilation)
    print(f"  Warming up ({n_warmup} runs)...")
    for i in range(n_warmup):
        detector.detect(frames[i % len(frames)])

    # Benchmark
    times = []
    det_counts = []
    for i in range(n_runs):
        frame = frames[i % len(frames)]
        t0 = time.perf_counter()
        dets = detector.detect(frame)
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000
        times.append(elapsed_ms)
        det_counts.append(len(dets))

    _print_stats("detect()", times)
    print(f"  Detections per frame: min={min(det_counts)}, max={max(det_counts)}, avg={statistics.mean(det_counts):.1f}")

    # Benchmark just preprocessing
    preprocess_times = []
    for i in range(n_runs):
        frame = frames[i % len(frames)]
        t0 = time.perf_counter()
        detector._preprocess(frame)
        t1 = time.perf_counter()
        preprocess_times.append((t1 - t0) * 1000)

    _print_stats("_preprocess() only", preprocess_times)

    return detector


def benchmark_tracker(detector, frames: list[np.ndarray], n_runs: int = 20):
    """Benchmark BoT-SORT tracking."""
    from engine.vision.tracker import Tracker
    from engine.vision.detector import Detector
    print("\n" + "="*60)
    print("BENCHMARK: Tracker (BoT-SORT)")
    print("="*60)

    tracker = Tracker()

    # Pre-detect all frames
    all_dets = []
    for frame in frames:
        dets = detector.detect(frame)
        person_dets = [d for d in dets if Detector.is_person(d)]
        all_dets.append(person_dets)

    times = []
    track_counts = []
    for i in range(n_runs):
        idx = i % len(frames)
        frame = frames[idx]
        dets = all_dets[idx]
        t0 = time.perf_counter()
        tracks = tracker.update(dets, frame)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
        track_counts.append(len(tracks))

    _print_stats("tracker.update()", times)
    print(f"  Tracks per frame: min={min(track_counts)}, max={max(track_counts)}, avg={statistics.mean(track_counts):.1f}")

    return tracker


def benchmark_reid(frames: list[np.ndarray], detector, n_runs: int = 15):
    """Benchmark Re-ID embedding extraction."""
    from engine.vision.reid import ReIDEngine
    from engine.vision.detector import Detector
    from engine.config import settings
    print("\n" + "="*60)
    print("BENCHMARK: Re-ID (OSNet-AIN)")
    print("="*60)

    model_path = os.path.join(settings.models_dir, settings.reid_model)
    reid = ReIDEngine(model_path=model_path)

    # Find frames with person detections and extract crops
    crops = []
    for frame in frames:
        dets = detector.detect(frame)
        h, w = frame.shape[:2]
        for d in dets:
            if not Detector.is_person(d):
                continue
            x1, y1, x2, y2 = d.bbox
            x1c, y1c = max(0, x1), max(0, y1)
            x2c, y2c = min(w, x2), min(h, y2)
            crop_h = y2c - y1c
            crop_w = x2c - x1c
            if crop_h >= 64 and crop_w >= 48:
                crops.append(frame[y1c:y2c, x1c:x2c])
        if len(crops) >= 10:
            break

    if not crops:
        # Fallback: create a synthetic person-sized crop
        print("  No real person crops found — using synthetic 128x256 crops")
        for _ in range(5):
            crops.append(np.random.randint(0, 255, (256, 128, 3), dtype=np.uint8))

    print(f"  Testing with {len(crops)} person crops")
    for i, c in enumerate(crops[:5]):
        print(f"    Crop {i}: {c.shape[1]}x{c.shape[0]}")

    # Warmup
    for c in crops[:2]:
        reid.extract_embedding(c)

    # Benchmark extract_embedding
    extract_times = []
    for i in range(n_runs):
        crop = crops[i % len(crops)]
        t0 = time.perf_counter()
        emb, quality = reid.extract_embedding(crop)
        t1 = time.perf_counter()
        extract_times.append((t1 - t0) * 1000)

    _print_stats("extract_embedding()", extract_times)

    # Benchmark get_or_create_global_id (includes FAISS search)
    gid_times = []
    for i in range(n_runs):
        crop = crops[i % len(crops)]
        emb, quality = reid.extract_embedding(crop)
        t0 = time.perf_counter()
        gid = reid.get_or_create_global_id("test_cam", i, emb, quality)
        t1 = time.perf_counter()
        gid_times.append((t1 - t0) * 1000)

    _print_stats("get_or_create_global_id()", gid_times)

    # Benchmark just preprocessing (CLAHE + resize)
    preproc_times = []
    for i in range(n_runs):
        crop = crops[i % len(crops)]
        t0 = time.perf_counter()
        reid._preprocess(crop)
        t1 = time.perf_counter()
        preproc_times.append((t1 - t0) * 1000)

    _print_stats("reid._preprocess() (CLAHE+resize)", preproc_times)

    return reid


def benchmark_face(frames: list[np.ndarray], detector, n_runs: int = 10):
    """Benchmark InsightFace recognition."""
    from engine.vision.face import FaceRecognizer
    from engine.vision.detector import Detector
    print("\n" + "="*60)
    print("BENCHMARK: Face Recognition (InsightFace)")
    print("="*60)

    try:
        face = FaceRecognizer()
    except Exception as e:
        print(f"  SKIP — FaceRecognizer init failed: {e}")
        return None

    # Get person crops
    crops = []
    for frame in frames:
        dets = detector.detect(frame)
        h, w = frame.shape[:2]
        for d in dets:
            if not Detector.is_person(d):
                continue
            x1, y1, x2, y2 = d.bbox
            x1c, y1c = max(0, x1), max(0, y1)
            x2c, y2c = min(w, x2), min(h, y2)
            if (y2c - y1c) >= 64 and (x2c - x1c) >= 48:
                crops.append(frame[y1c:y2c, x1c:x2c])
        if len(crops) >= 5:
            break

    if not crops:
        crops = [np.random.randint(0, 255, (256, 128, 3), dtype=np.uint8) for _ in range(3)]
    print(f"  Testing with {len(crops)} crops")

    # Warmup
    for c in crops[:1]:
        face.analyze(c)

    times = []
    for i in range(n_runs):
        crop = crops[i % len(crops)]
        t0 = time.perf_counter()
        results = face.analyze(crop)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    _print_stats("face.analyze()", times)
    return face


def benchmark_weapon(frames: list[np.ndarray], detector, n_runs: int = 20):
    """Benchmark weapon detection check."""
    from engine.vision.weapon import WeaponDetector
    print("\n" + "="*60)
    print("BENCHMARK: Weapon Detector")
    print("="*60)

    try:
        weapon = WeaponDetector()
    except Exception as e:
        print(f"  SKIP — WeaponDetector init failed: {e}")
        return None

    # Pre-detect
    all_dets = [detector.detect(f) for f in frames]

    times = []
    for i in range(n_runs):
        idx = i % len(frames)
        t0 = time.perf_counter()
        weapon.check(all_dets[idx], "test_cam")
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    _print_stats("weapon.check()", times)
    return weapon


def benchmark_annotation(frames: list[np.ndarray], detector, n_runs: int = 20):
    """Benchmark frame annotation (drawing boxes, zones, status bar)."""
    from engine.pipeline import _draw_annotations
    from engine.vision.tracker import Tracker
    from engine.vision.detector import Detector
    print("\n" + "="*60)
    print("BENCHMARK: Annotation Drawing")
    print("="*60)

    tracker = Tracker()

    # Build some tracks
    tracks_list = []
    for frame in frames:
        dets = detector.detect(frame)
        person_dets = [d for d in dets if Detector.is_person(d)]
        tracks = tracker.update(person_dets, frame)
        if tracks:
            tracks_list.append((frame.copy(), tracks))
        if len(tracks_list) >= 5:
            break

    if not tracks_list:
        print("  SKIP — no tracks to annotate")
        return

    times = []
    for i in range(n_runs):
        frame, tracks = tracks_list[i % len(tracks_list)]
        test_frame = frame.copy()  # Copy because _draw_annotations modifies in-place
        t0 = time.perf_counter()
        _draw_annotations(test_frame, tracks, [], "test_cam", 15.0)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    _print_stats("_draw_annotations()", times)


def benchmark_jpeg_encode(frames: list[np.ndarray], n_runs: int = 30):
    """Benchmark JPEG encoding at different quality levels."""
    print("\n" + "="*60)
    print("BENCHMARK: JPEG Encoding")
    print("="*60)

    for quality in [60, 70, 80, 90]:
        times = []
        sizes = []
        for i in range(n_runs):
            frame = frames[i % len(frames)]
            t0 = time.perf_counter()
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000)
            if ok:
                sizes.append(len(buf))
        avg_size_kb = statistics.mean(sizes) / 1024
        _print_stats(f"imencode(quality={quality}) [{avg_size_kb:.0f}KB avg]", times)


def benchmark_full_pipeline(frames: list[np.ndarray], n_runs: int = 15):
    """Simulate the full pipeline loop and measure end-to-end timing."""
    from engine.vision.detector import Detector, Detection
    from engine.vision.tracker import Tracker
    from engine.vision.reid import ReIDEngine
    from engine.pipeline import _draw_annotations
    from engine.config import settings
    print("\n" + "="*60)
    print("BENCHMARK: Full Pipeline (detect → track → reid → annotate → encode)")
    print("="*60)

    detector = Detector()
    tracker = Tracker()
    model_path = os.path.join(settings.models_dir, settings.reid_model)
    reid = ReIDEngine(model_path=model_path)

    # Warmup
    for f in frames[:3]:
        dets = detector.detect(f)
        person_dets = [d for d in dets if Detector.is_person(d)]
        tracks = tracker.update(person_dets, f)

    stage_times = {
        "detect": [], "track": [], "reid": [],
        "annotate": [], "encode": [], "total": []
    }

    for i in range(n_runs):
        frame = frames[i % len(frames)].copy()
        h, w = frame.shape[:2]
        t_total_start = time.perf_counter()

        # detect
        t0 = time.perf_counter()
        dets = detector.detect(frame)
        stage_times["detect"].append((time.perf_counter() - t0) * 1000)

        person_dets = [d for d in dets if Detector.is_person(d)]

        # track
        t0 = time.perf_counter()
        tracks = tracker.update(person_dets, frame)
        stage_times["track"].append((time.perf_counter() - t0) * 1000)

        # reid (per track)
        t0 = time.perf_counter()
        global_ids = {}
        for track in tracks:
            x1, y1, x2, y2 = track.bbox
            x1c, y1c = max(0, x1), max(0, y1)
            x2c, y2c = min(w, x2), min(h, y2)
            crop_h = y2c - y1c
            crop_w = x2c - x1c
            if crop_h < 64 or crop_w < 48 or crop_w > crop_h * 3:
                continue
            crop = frame[y1c:y2c, x1c:x2c]
            try:
                emb, q = reid.extract_embedding(crop)
                gid = reid.get_or_create_global_id("bench_cam", track.track_id, emb, q)
                global_ids[track.track_id] = gid
            except Exception:
                pass
        stage_times["reid"].append((time.perf_counter() - t0) * 1000)

        # annotate
        t0 = time.perf_counter()
        annotated = _draw_annotations(frame, tracks, [], "bench_cam", 15.0, global_ids=global_ids)
        stage_times["annotate"].append((time.perf_counter() - t0) * 1000)

        # jpeg encode
        t0 = time.perf_counter()
        cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        stage_times["encode"].append((time.perf_counter() - t0) * 1000)

        stage_times["total"].append((time.perf_counter() - t_total_start) * 1000)

    print("\n  Stage breakdown (per frame):")
    total_avg = 0
    for stage in ["detect", "track", "reid", "annotate", "encode"]:
        avg = statistics.mean(stage_times[stage])
        total_avg += avg
        med = statistics.median(stage_times[stage])
        mx = max(stage_times[stage])
        pct = (avg / statistics.mean(stage_times["total"])) * 100
        print(f"    {stage:>10s}: avg={avg:6.1f}ms  med={med:6.1f}ms  max={mx:6.1f}ms  ({pct:4.1f}%)")

    print(f"    {'TOTAL':>10s}: avg={statistics.mean(stage_times['total']):6.1f}ms  → {1000/statistics.mean(stage_times['total']):.1f} FPS theoretical max")
    print(f"\n  With skip_every=3: effective AI FPS = {1000/statistics.mean(stage_times['total']):.1f}, stream FPS = {3 * 1000/statistics.mean(stage_times['total']):.1f}")


def _print_stats(label: str, times_ms: list[float]):
    """Print timing statistics."""
    avg = statistics.mean(times_ms)
    med = statistics.median(times_ms)
    mn = min(times_ms)
    mx = max(times_ms)
    std = statistics.stdev(times_ms) if len(times_ms) > 1 else 0
    print(f"  {label}:")
    print(f"    avg={avg:.1f}ms  med={med:.1f}ms  min={mn:.1f}ms  max={mx:.1f}ms  std={std:.1f}ms")


if __name__ == "__main__":
    print("SENTINAL v2 — Pipeline Benchmark")
    print("=" * 60)

    frames = load_test_frames()

    # Individual component benchmarks
    detector = benchmark_detector(frames)
    tracker = benchmark_tracker(detector, frames)
    reid = benchmark_reid(frames, detector)
    face = benchmark_face(frames, detector)
    weapon = benchmark_weapon(frames, detector)
    benchmark_annotation(frames, detector)
    benchmark_jpeg_encode(frames)

    # Full pipeline simulation
    benchmark_full_pipeline(frames)

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
