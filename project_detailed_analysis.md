# SENTINALv1 — Detailed Project Analysis

## 1. Executive Overview

SENTINALv1 is a local-first, CPU-efficient, open-source AI surveillance platform. It uses computer vision to detect people in real time, track them across frames, detect zone intrusions, and fire alerts — all without cloud dependencies.

The project is structured as a **monorepo** with three distinct layers:

- **Core Engine** (`sentinal/` + `gui.py`) — Python inference pipeline
- **Backend API** (`backend/`) — FastAPI REST+streaming server
- **Frontend Dashboard** (`frontend/`) — React/Vite web UI

---

## 2. Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    User Interfaces                         │
│  ┌─────────────────────┐   ┌──────────────────────────┐   │
│  │  PyQt5 Desktop GUI  │   │  React/Vite Web Dashboard │  │
│  └────────┬────────────┘   └────────────┬─────────────┘   │
│           │                             │ HTTP/MJPEG        │
│           └──────────┐   ┌─────────────┘                   │
│                      ▼   ▼                                  │
│             ┌──────────────────┐                            │
│             │  FastAPI Backend │  :8000                     │
│             │  /stream /events │                            │
│             │  /zones /health  │                            │
│             └────────┬─────────┘                           │
│                      │                                      │
│             ┌────────▼──────────────────────────────────┐  │
│             │         SurveillancePipeline               │  │
│             │  VideoSource → Tracker → IdStitcher →     │  │
│             │  ZoneManager → AlertManager → DrawOverlays │  │
│             └───────────────────────────────────────────┘  │
│                      │                        │             │
│            ┌─────────▼──────┐   ┌────────────▼──────────┐  │
│            │   PostgreSQL   │   │  CSV + JPEG Snapshots  │  │
│            └────────────────┘   └────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

---

## 3. Module-by-Module Analysis

### 3.1 `config.py`

- **Pattern**: Dataclass-based config that reads from `.env` via `python-dotenv`.
- **Strengths**: Clean, typed, composable. All overridable via environment variables.
- **Issue**: `VIDEO_SOURCE_TYPE` env var returns a `str` but the field is typed as `Literal["webcam", "video"]` — no runtime validation enforced.

### 3.2 `sentinal/video_source.py`

- **Pattern**: Background thread continuously reads from `cv2.VideoCapture` into a bounded deque (maxlen=2).
- **Strengths**: Non-blocking read, drops stale frames, CAP_DSHOW on Windows for faster init, BUFFERSIZE=1.
- **Issue**: Uses `time.sleep(0.002)` polling — slightly wasteful; `threading.Condition` would be cleaner.

### 3.3 `sentinal/tracker.py`

- **Pattern**: Wraps `ultralytics YOLO.track()` with `persist=True` and `classes=[0]` (persons only).
- **Strengths**: ByteTrack integration, model fusion for faster CPU inference.
- **Issue**: No warmup run on model load — first frame always slow.

### 3.4 `sentinal/id_stitcher.py`

- **Pattern**: `TrackIdStitcher` uses **MobileNetV3-Small** to extract 576-dim embeddings from person crops. Cosine similarity against a TTL-bounded `_lost` pool re-identifies people after they leave frame.
- **Strengths**: Robust to lighting/angle changes vs. old histograms. Batched inference.
- **Issue**: MobileNetV3 is ImageNet-pretrained, not a person Re-ID model — it doesn't encode person-specific features (gait, clothing texture) as reliably as a dedicated Re-ID model (e.g., OSNet, BoT-Transreid). Similarity thresholds (0.60) may cause false matches in crowded scenes.

### 3.5 `sentinal/zones.py`

- **Pattern**: Polygon hit-testing using `point_in_polygon` (ray-casting). Raises `ZoneEvent` only on first entry, suppresses duplicates via `active_ids`.
- **Strengths**: Stateless per-frame logic, efficient single-pass track iteration.
- **Issue**: Zones are hardcoded in `config.py` `load_config()`. They can't be edited at runtime from the UI.

### 3.6 `sentinal/alerts.py`

- **Pattern**: Deduplicates events via `(track_id, zone_id)` key + cooldown timer. Snapshot saves and DB inserts are fire-and-forget daemon threads.
- **Strengths**: Non-blocking alert handling, batched CSV writes, thread-safe.
- **Issue**: Daemon threads have no error callback — silent failures on disk full or DB down. No retry logic.

### 3.7 `sentinal/db.py`

- **Pattern**: Bare `psycopg2` with per-call `connect()`.
- **Issue**: Opens a new TCP connection on every insert. No connection pooling. Will be a bottleneck at high alert rates or when DB is remote.

### 3.8 `sentinal/pipeline.py`

- **Pattern**: Generator-based frame loop. Calls tracker → stitcher → zones → alerts in sequence. EMA FPS display.
- **Strengths**: Clean separation of concerns, easy to extend.
- **Issue**: All stages run **sequentially in one thread**. Heavy MobileNet inference on every frame blocks the loop.

### 3.9 `backend/`

- **Pattern**: FastAPI with `lifespan` context managing `VideoStreamManager` singleton. MJPEG stream served from `/stream/{camera_id}`.
- `video_service.py` encodes frames with `cv2.imencode('.jpg')` and shares via a lock.
- **Issue**: MJPEG frames are polled with `time.sleep(0.03)` (static 33ms), not use webcam FPS. No real-time frame push mechanism (WebSocket would be better). The `video_service.py` starts **a separate pipeline instance** from `gui.py` — meaning two competing instances trying to open the camera.

### 3.10 `frontend/`

- **Pattern**: React + Vite SPA. `Dashboard.jsx` shows `LiveStream` (MJPEG `<img>`) and `EventLog` (HTTP polling every 2s).
- **Issue**: `cameraId` is hardcoded as `"cam_01"` in `Dashboard.jsx`. `EventLog` uses REST polling — no real-time WebSocket push. `"View Snapshot"` link is not functional (no `<a>` tag or image preview).

### 3.11 `gui.py`

- **Pattern**: PyQt5 `QThread` consuming the pipeline generator, rendering frames to a `QLabel`.
- **Issue**: Each time "Start" is clicked, a new `VideoConfig` is constructed **without inheriting `frame_skip`, `frame_width`, `frame_height`** from the loaded config, resetting them to defaults.

---

## 4. Infrastructure

### Docker

- `Dockerfile.backend` + `docker-compose.yml` sets up backend + PostgreSQL.
- Frontend Docker setup (`frontend/Dockerfile.frontend` with nginx) present but backend Compose doesn't build the frontend.
- **Issue**: Backend container performs `sys.path.append(parent)` hack — fragile in containerized environments where package structure differs.

### Dependencies

`requirements.txt` is incomplete — missing `fastapi`, `uvicorn`, `torch`, `torchvision`, `psycopg2-binary`, `PyQt5` (only has `pyyaml`, `ultralytics`, `opencv-python`, `numpy`, `PyQt5`). This will cause `pip install -r requirements.txt` to be broken for a fresh environment.

---

## 5. Data Flow Summary

```
Webcam Frame
    │
    ▼
VideoSource (thread, maxlen=2 buffer)
    │
    ▼
ObjectTracker (YOLOv8n ByteTrack) → List[{track_id, bbox, conf}]
    │
    ▼
TrackIdStitcher (MobileNetV3 embed, cosine sim) → adds stable_id
    │
    ▼
ZoneManager (polygon hit-test) → List[ZoneEvent]
    │
    ▼
AlertManager (dedup, async CSV+JPEG+DB)
    │
    ▼
draw_overlays → display_frame (PyQt5 or MJPEG)
```

---

## 6. Technology Stack Summary

| Layer            | Technology                             |
| ---------------- | -------------------------------------- |
| Detection        | YOLOv8n (Ultralytics)                  |
| Tracking         | ByteTrack (via Ultralytics)            |
| Re-ID            | MobileNetV3-Small (torchvision)        |
| Backend          | Python 3.12, FastAPI, uvicorn          |
| Frontend         | React 18, Vite, lucide-react, date-fns |
| DB               | PostgreSQL (psycopg2), fallback CSV    |
| GUI              | PyQt5                                  |
| Containerization | Docker, docker-compose                 |
| Config           | python-dotenv, dataclasses             |
