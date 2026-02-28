# SENTINALv1 — Known Issues and Mistakes

> This document catalogues current bugs, design mistakes, and technical debt. Issues are rated by severity: 🔴 Critical · 🟡 Medium · 🟢 Minor.

---

## 🔴 Critical Issues

### ISSUE-01: Two Competing Pipeline Instances
**Location**: `backend/services/video_service.py` + `gui.py`  
**Problem**: `VideoStreamManager` in `video_service.py` instantiates a `SurveillancePipeline` which opens `cv2.VideoCapture(0)`. When `gui.py` is also running, both processes compete for the same webcam device. On Windows, only one can hold the device at a time — one will silently fail to open the camera.  
**Impact**: Backend MJPEG stream returns black frames or errors when gui.py is running. Completely breaks the full-stack experience.

### ISSUE-02: `requirements.txt` Is Incomplete
**Location**: `requirements.txt`  
**Problem**: Missing `fastapi`, `uvicorn`, `torch`, `torchvision`, `psycopg2-binary`, `pydantic-settings`, `python-dotenv`. Running `pip install -r requirements.txt` on a fresh machine will fail at import time.  
**Impact**: Onboarding new developers or CI/CD pipelines will fail immediately.

### ISSUE-03: No Connection Pooling in `db.py`
**Location**: `sentinal/db.py`  
**Problem**: `insert_event()` calls `psycopg2.connect()` on every alert, opening and closing a full TCP connection each time. Alerts can fire rapidly (every 10 seconds per track), and each call opens a fresh socket.  
**Impact**: High latency on DB inserts, risk of connection exhaustion under load, and connection leak if an exception occurs mid-connect.

---

## 🟡 Medium Issues

### ISSUE-04: `gui.py` Loses Config on Restart
**Location**: `gui.py` `_start_pipeline()` method (line 86–89)  
**Problem**: On each "Start" click a new `VideoConfig` is created with only `source_type` and `video_path` — `frame_skip`, `frame_width`, `frame_height` all revert to their dataclass defaults (or `None`), discarding any values from `.env`.  
**Impact**: Frame skip and resolution settings silently reset to defaults every time the user presses Start.

### ISSUE-05: Zones Are Hardcoded in Python
**Location**: `config.py` `load_config()` (line 107–113)  
**Problem**: The single "Entrance" zone polygon is hardcoded as `[(100, 80), (540, 80), (540, 300), (100, 300)]`. Changing it requires editing source code and restarting.  
**Impact**: Non-technical users cannot adjust detection zones. Zones cannot be configured at runtime via the web UI.

### ISSUE-06: MobileNetV3 Is Not a Re-ID Model
**Location**: `sentinal/id_stitcher.py`  
**Problem**: MobileNetV3 was trained on ImageNet (1000 general object classes). It is not optimised to distinguish between different people, making it prone to false positives (two different people matching) in environments where people wear similar clothing.  
**Impact**: Re-ID stitching may assign the same `stable_id` to two different people wearing similar clothing, or fail to match the same person after a change in appearance.

### ISSUE-07: Re-ID Features Extracted Twice Per Frame
**Location**: `sentinal/id_stitcher.py` `assign()` method  
**Problem**: `_compute_batch_features()` is called once for the matching step (line 81) and then again for the `_upsert_lost()` update step (line 109–113) — extracting features for the same tracks twice per frame.  
**Impact**: Double the inference work per frame, contributing to latency on CPU.

### ISSUE-08: Frontend EventLog Has Broken Snapshot Preview
**Location**: `frontend/src/components/EventLog.jsx` line 61–65  
**Problem**: The "View Snapshot" button is a `<div>` with no actual link, click handler, or image source. It renders text with an icon but does nothing when clicked.  
**Impact**: Users cannot view intrusion snapshots from the web UI.

### ISSUE-09: Backend CORS Is Completely Open
**Location**: `backend/main.py` (line 26–31)  
**Problem**: `allow_origins=settings.backend_cors_origins` — if the default allows `"*"`, the backend accepts requests from any origin. Even on a LAN-only deployment this is unnecessarily permissive.  
**Impact**: Any website on the local network can make authenticated requests to the backend.

### ISSUE-10: Frontend `cameraId` Hardcoded
**Location**: `frontend/src/pages/Dashboard.jsx` line 10  
**Problem**: `const cameraId = "cam_01"` is hardcoded. It must match `CAMERA_ID` in `.env` exactly or the stream returns a 404.  
**Impact**: Confusing for users. If `CAMERA_ID` is changed in `.env`, the frontend silently shows nothing.

---

## 🟢 Minor Issues

### ISSUE-11: No Model Warm-Up
**Location**: `sentinal/tracker.py`  
**Problem**: YOLO is not run on a dummy frame after load. The first real frame always takes 2–3× longer due to JIT compilation.  
**Impact**: FPS drops sharply on the first frame, confusing the FPS display.

### ISSUE-12: `VideoSource` Busy-Polls with `time.sleep`
**Location**: `sentinal/video_source.py`  
**Problem**: The `read()` method polls the queue with `time.sleep(0.002)` in a loop instead of using a `threading.Condition` or `queue.Queue` with `get(timeout=...)`.  
**Impact**: Wastes a tiny amount of CPU in tight poll loops.

### ISSUE-13: Silent Failures in Alert Daemon Threads
**Location**: `sentinal/alerts.py` `handle_alerts()`  
**Problem**: Background threads for snapshot saves and DB inserts have no completion callback or failure notification. If a disk is full or the DB is unavailable, errors go completely unlogged at the `WARNING` level — they are swallowed by the generic logger in `db.py`.  
**Impact**: Alerts appear logged in the terminal but the JPEG and DB record silently don't exist.

### ISSUE-14: `sys.path.append` Hack in Backend
**Location**: `backend/main.py` line 5  
**Problem**: `sys.path.append(str(Path(__file__).resolve().parent.parent))` is a runtime path manipulation so `sentinal` and `config` are importable. This is fragile in Docker when the working directory or package structure differs.  
**Impact**: Docker deployment may silently fail with `ModuleNotFoundError` if paths shift.

### ISSUE-15: No Logging for Re-ID Match/Miss in Production
**Location**: `sentinal/id_stitcher.py` `_best_match()`  
**Problem**: There is a `DEBUG`-level log line added during debugging but no production-level observability: you can't tell from logs whether Re-ID matched or created a new ID, making tuning the threshold blind.  
**Impact**: Impossible to tune similarity threshold without reading debug logs.
