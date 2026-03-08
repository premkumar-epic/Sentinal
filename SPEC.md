# SENTINAL v2 — Feature Specification

> **What this file is:** The complete technical specification for every feature in SENTINAL v2.  
> **Who reads it:** Claude Code, at the start of any session where you reference it.  
> **How to reference it:** Start your prompt with "Read CLAUDE.md and SPEC.md first."  
> **Rule:** CLAUDE.md = rules. SPEC.md = what to build. Never mix them.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Hardware & Environment](#2-hardware--environment)
3. [Configuration System](#3-configuration-system)
4. [Stream Layer](#4-stream-layer)
5. [AI Vision Pipeline](#5-ai-vision-pipeline)
6. [Zone System](#6-zone-system)
7. [Alert System](#7-alert-system)
8. [Storage Layer](#8-storage-layer)
9. [FastAPI Backend](#9-fastapi-backend)
10. [React Dashboard](#10-react-dashboard)
11. [Database Schema](#11-database-schema)
12. [Docker Deployment](#12-docker-deployment)
13. [Requirements & Dependencies](#13-requirements--dependencies)
14. [Phase Build Order](#14-phase-build-order)

---

## 1. System Overview

SENTINAL v2 is a **zero-cloud, on-premise AI video surveillance system**. All processing happens locally on the AI server. No data leaves the local network.

### What the system does:
- Ingests video from multiple cameras (DroidCam HTTP streams / IP Webcam RTSP / webcam)
- Detects and tracks people in real-time across all camera feeds simultaneously
- Detects weapons (knives, guns) in any camera feed
- Fires a full-screen alarm when a weapon is detected
- Defines polygon zones per camera; fires alerts when people enter restricted zones
- Re-identifies the same person across different cameras using body appearance (OSNet-AIN)
- Recognizes and names known faces using InsightFace buffalo_l
- Detects anomalies: loitering, overcrowding, violence posture
- Logs all events (intrusion, weapon, face match, anomaly) to a database with JPEG snapshots
- Sends email and/or webhook notifications for critical events
- Streams all camera feeds live to a React web dashboard over the local network
- Pushes real-time event alerts to the dashboard via WebSocket

### Architecture layers (bottom to top):
```
Layer 1: STREAM     — VideoSource per camera (threaded, auto-reconnect)
Layer 2: AI ENGINE  — Detection → Tracking → Re-ID → Face → Zones → Anomaly → Weapon
Layer 3: API        — FastAPI (REST + WebSocket + MJPEG streaming)
Layer 4: DASHBOARD  — React 18 + Vite (any browser on local network)
```

### Data flow per frame:
```
Camera feed
  → VideoSource (thread, deque maxlen=2, CAP_PROP_BUFFERSIZE=1)
  → YOLO11n detection (person + weapon classes)
  → BoT-SORT tracking (local track IDs per camera)
  → [if tracked person] Zone check (ray-casting, bottom-center of bbox)
  → [if zone intrusion or weapon] OSNet-AIN Re-ID (cross-camera global ID)
  → [if face visible] InsightFace face recognition (name lookup)
  → [if anomaly rule fires] Anomaly flag
  → AlertManager (dedup, cooldown, dispatch)
  → [async] DB write + snapshot save + WebSocket push + email/webhook
  → MJPEG frame buffer (annotated frame → browser)
```

---

## 2. Hardware & Environment

### AI Server (RTX 4050 laptop)
- Runs: entire Python engine, FastAPI backend, PostgreSQL
- GPU: NVIDIA RTX 4050 6GB VRAM — all YOLO inference runs on CUDA
- All models loaded to CUDA at startup, not per-frame

### Browser Client (Zenbook 14 or any device)
- Opens: `http://[RTX-4050-IP]:5173` in any browser
- Runs zero AI — pure React dashboard

### Cameras
- Primary: Android phones running **IP Webcam** app (provides RTSP)
- Fallback: Android phones running **DroidCam** app (HTTP MJPEG)
- Fallback: USB webcam (cv2.VideoCapture(0))
- Camera URL examples:
  - IP Webcam RTSP: `rtsp://192.168.1.x:8080/h264_ulaw.sdp`
  - IP Webcam HTTP: `http://192.168.1.x:8080/video`
  - DroidCam HTTP: `http://192.168.1.x:4747/video`

### Network
- All devices on the same WiFi network
- Use 5GHz band for cameras to minimize stream jitter
- Server runs on static local IP (set via router DHCP reservation)

---

## 3. Configuration System

### File: `engine/config.py`

Use **Pydantic BaseSettings** to load all config from `.env` file. Never hardcode values.

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Models
    yolo_model: str = "yolo11n.pt"          # yolo11n.pt or yolo11m.pt
    yolo_conf: float = 0.40
    yolo_iou: float = 0.45
    reid_model: str = "osnet_ain_x1_0_msmt17.pth"
    reid_threshold: float = 0.75            # cosine similarity threshold
    face_model: str = "buffalo_l"           # InsightFace model pack
    face_quality_threshold: float = 0.5    # skip crops below this quality
    
    # Paths
    models_dir: str = "models/"
    snapshots_dir: str = "data/snapshots/"
    zones_file: str = "data/zones.json"
    logs_dir: str = "data/logs/"
    
    # Database
    db_url: str = "sqlite:///data/sentinal.db"  # Phase 1-4; swap to postgres in Phase 5
    
    # Alerts
    alert_cooldown_seconds: int = 60
    alert_email_enabled: bool = False
    alert_email_smtp_host: str = ""
    alert_email_smtp_port: int = 587
    alert_email_sender: str = ""
    alert_email_password: str = ""
    alert_email_recipient: str = ""
    alert_webhook_enabled: bool = False
    alert_webhook_url: str = ""
    
    # Anomaly thresholds
    loitering_seconds: int = 30             # person in zone > 30s = loitering
    crowd_threshold: int = 5               # N+ persons in zone = crowding
    
    # Stream
    stream_fps_target: int = 15
    stream_reconnect_error_threshold: int = 5
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### File: `.env` (never commit — add to .gitignore)
```
YOLO_MODEL=yolo11n.pt
YOLO_CONF=0.40
DB_URL=sqlite:///data/sentinal.db
ALERT_EMAIL_ENABLED=false
```

---

## 4. Stream Layer

### File: `engine/stream/source.py`

**Class: `VideoSource`**

Responsibilities:
- Opens a video stream (any OpenCV-compatible URL)
- Reads frames continuously in a background daemon thread
- Stores only the latest frame (deque maxlen=2)
- Auto-reconnects on stream failure with exponential backoff
- Never blocks the caller — `get_latest_frame()` returns immediately

```python
# Interface
class VideoSource:
    def __init__(self, url: str, cam_id: str): ...
    def start(self) -> None: ...           # starts background thread
    def stop(self) -> None: ...            # stops background thread
    def get_latest_frame(self) -> Optional[np.ndarray]: ...  # None if no frame
    def is_alive(self) -> bool: ...        # True if thread running and stream healthy
```

**Critical requirements:**
- `cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)` — ALWAYS. Without this frames are 2–5s old.
- `cap.set(cv2.CAP_PROP_FPS, 15)` — don't request more than DroidCam gives
- Reconnect logic: on read failure → sleep with exponential backoff: 2→4→8→16→32s. Never give up — keeps retrying forever until stopped. After `stream_reconnect_error_threshold` attempts, it starts logging an ERROR instead of a WARNING to signal persistent connection issues.
- Thread must be `daemon=True` so it dies when the main process exits
- Use `threading.Event` for stop signal — never `time.sleep()` in the loop
- `is_alive()` returns True as long as the capture thread is running (even if currently reconnecting).

### File: `engine/stream/mjpeg.py`

**Class: `MJPEGBuffer`**

Responsibilities:
- Accepts annotated frames from the AI pipeline
- JPEG-encodes each frame
- Serves frames as multipart HTTP stream to FastAPI

```python
class MJPEGBuffer:
    def __init__(self, cam_id: str): ...
    def push_frame(self, frame: np.ndarray) -> None: ...
    async def frame_generator(self) -> AsyncGenerator[bytes, None]: ...
```

The `frame_generator` yields bytes in multipart format:
```
b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
```

Use `asyncio.Queue(maxsize=2)` internally. If queue is full, drop the oldest frame (non-blocking put).

---

## 5. AI Vision Pipeline

### File: `engine/vision/detector.py`

**Class: `Detector`**

Wraps YOLO11n (or YOLO11m) for person and weapon detection.

```python
from dataclasses import dataclass

@dataclass
class Detection:
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2
    confidence: float
    class_id: int                      # 0=person, weapon_class_ids vary
    class_name: str                    # "person", "knife", "gun", etc.

class Detector:
    def __init__(self, model_path: str, device: str = "cuda"): ...
    def detect(self, frame: np.ndarray) -> list[Detection]: ...
```

**Requirements:**
- Load model once at `__init__`, not per frame
- `device="cuda"` by default; fall back to `"cpu"` if CUDA not available
- Filter by `conf >= settings.yolo_conf`
- Person class_id = 0 (COCO standard)
- Weapon classes: knife=43, gun/pistol varies — detect class_name containing "knife", "gun", "pistol", "rifle", "weapon"
- Return persons and weapons as separate lists for the pipeline to handle

### File: `engine/vision/tracker.py`

**Class: `Tracker`**

Wraps BoT-SORT from Ultralytics.

```python
@dataclass
class Track:
    track_id: int                      # stable local ID per camera
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2
    confidence: float

class Tracker:
    def __init__(self): ...
    def update(self, detections: list[Detection], frame: np.ndarray) -> list[Track]: ...
```

**Requirements:**
- Use Ultralytics BoT-SORT: `from ultralytics import YOLO` then `model.track()`
- Or use boxmot library: `from boxmot import BoTSORT`
- Track IDs must be stable across frames while person is visible
- When a person exits and re-enters frame, BoT-SORT will assign a new local ID (that's expected — Re-ID handles cross-entry identity)

### File: `engine/vision/reid.py`

**Class: `ReIDEngine`**

Cross-camera person re-identification using OSNet-AIN + FAISS.

```python
class ReIDEngine:
    def __init__(self, model_path: str): ...
    
    def extract_embedding(self, crop: np.ndarray) -> np.ndarray: ...
    # Returns 512-d normalized float32 vector
    
    def get_or_create_global_id(
        self, 
        local_cam_id: str, 
        local_track_id: int, 
        embedding: np.ndarray
    ) -> str: ...
    # Returns global_id (UUID string) — same person across cameras gets same global_id
    
    def update_embedding(self, global_id: str, new_embedding: np.ndarray) -> None: ...
    # EMA update: stored = 0.90 * stored + 0.10 * new_embedding, then re-normalize
```

**Internal state:**
- `self.gallery`: FAISS IndexFlatIP (cosine similarity via normalized vectors)
- `self.id_map`: dict mapping FAISS index → global_id
- `self.lost_pool`: dict of `{global_id: (embedding, expire_time)}` — re-entry within 30s restores identity
- `self.local_to_global`: dict of `{(cam_id, local_track_id): global_id}`

**CLAHE preprocessing — apply before every embedding extraction:**
```python
def _preprocess(self, crop: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    crop = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
    crop = cv2.resize(crop, (128, 256))  # OSNet input size
    return crop
```

**Matching logic:**
- Query FAISS gallery with new embedding
- If top-1 cosine similarity > 0.75 → same person (use existing global_id)
- Else → new person (create new UUID global_id, add to gallery)
- On track loss: move to lost_pool with 30s TTL
- On new track: check lost_pool first before FAISS query

### File: `engine/vision/face.py`

**Class: `FaceRecognizer`**

Face detection + recognition using InsightFace.

```python
@dataclass
class FaceResult:
    bbox: tuple[int, int, int, int]
    embedding: np.ndarray              # 512-d ArcFace embedding
    quality_score: float               # 0.0–1.0
    name: Optional[str]                # None if unknown
    global_id: Optional[str]          # matched identity global_id if known

class FaceRecognizer:
    def __init__(self, model_pack: str = "buffalo_l"): ...
    def analyze(self, frame: np.ndarray) -> list[FaceResult]: ...
    def enroll(self, name: str, face_image: np.ndarray) -> str: ...
    # Returns global_id of enrolled identity
```

**Requirements:**
- Use `insightface.app.FaceAnalysis(name="buffalo_l")`
- Skip any face crop with `quality_score < settings.face_quality_threshold` (0.5)
- Match against known faces by cosine similarity > 0.6
- Face embeddings for known persons stored in DB `identities` table
- Load known embeddings from DB at startup; refresh on new enrollment

### File: `engine/vision/anomaly.py`

**Class: `AnomalyDetector`**

Rule-based anomaly detection — no extra ML model required.

```python
@dataclass
class Anomaly:
    type: str          # "loitering" | "crowding" | "violence"
    zone_id: str
    track_ids: list[int]
    detail: str        # human-readable description

class AnomalyDetector:
    def __init__(self): ...
    def update(self, tracks: list[Track], zone_events: dict) -> list[Anomaly]: ...
```

**Rules:**

**Loitering:**
- A single track_id stays inside the same zone for > `settings.loitering_seconds` (30s default)
- Implementation: maintain `{track_id: {zone_id: first_seen_timestamp}}`
- Fire once when threshold crossed; reset if person leaves zone

**Crowding:**
- More than `settings.crowd_threshold` (5 default) persons simultaneously in the same zone
- Fire once per minute while crowd persists

**Violence (posture heuristic):**
- Two tracks whose bboxes overlap by > 40% IoU for > 3 consecutive seconds
- This is a rough approximation — flag for human review, not automatic action

### File: `engine/vision/weapon.py`

**Class: `WeaponDetector`**

Filters YOLO detections for weapon classes and triggers the highest-priority alarm.

```python
@dataclass
class WeaponAlert:
    cam_id: str
    class_name: str    # "knife", "gun", etc.
    confidence: float
    bbox: tuple[int, int, int, int]
    snapshot_path: str

class WeaponDetector:
    def __init__(self): ...
    def check(self, detections: list[Detection], cam_id: str) -> Optional[WeaponAlert]: ...
```

**Requirements:**
- Weapon detection is the highest-priority alert — bypasses all cooldowns
- A weapon detection fires immediately regardless of the 60s alert cooldown
- Minimum confidence for weapon alert: 0.55 (higher than person detection to reduce false positives)
- The weapon alert triggers a special "RED ALARM" event type in the DB and WebSocket
- Dashboard shows full-screen AlertBanner on weapon detection

### File: `engine/pipeline.py`

**Class: `CameraPipeline`**

The main per-camera processing loop. This is the heart of the system.

```python
class CameraPipeline:
    def __init__(self, cam_id: str, source_url: str): ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def get_mjpeg_buffer(self) -> MJPEGBuffer: ...
```

**Pipeline loop (runs in a separate Process):**
```
while running:
    frame = video_source.get_latest_frame()
    if frame is None: continue
    
    detections = detector.detect(frame)
    
    weapon_alerts = weapon_detector.check(detections, cam_id)
    if weapon_alerts: dispatch_weapon_alert(weapon_alerts, frame)
    
    person_detections = [d for d in detections if d.class_name == "person"]
    tracks = tracker.update(person_detections, frame)
    
    zone_events = zone_manager.check_intrusions(tracks, cam_id)
    
    for track in tracks:
        crop = frame[y1:y2, x1:x2]
        embedding = reid_engine.extract_embedding(crop)
        global_id = reid_engine.get_or_create_global_id(cam_id, track.track_id, embedding)
        
        face_results = face_recognizer.analyze(crop)
        name = face_results[0].name if face_results else None
    
    anomalies = anomaly_detector.update(tracks, zone_events)
    
    for event in zone_events + anomalies:
        alert_manager.dispatch(event, frame, cam_id)
    
    annotated_frame = draw_annotations(frame, tracks, zone_overlays, labels)
    mjpeg_buffer.push_frame(annotated_frame)
```

**Frame annotation (`draw_annotations`):**
- Bounding boxes: green for tracked persons, red for weapons
- Track ID + global_id label above each box
- Name label if face recognized
- Zone polygons: green (safe), red (triggered)
- Small status bar at top: camera name, FPS, active tracks count

### File: `engine/manager.py`

**Class: `MultiCamManager`**

Manages all camera pipelines across the system.

```python
class MultiCamManager:
    def __init__(self): ...
    def add_camera(self, cam_id: str, url: str) -> None: ...
    def remove_camera(self, cam_id: str) -> None: ...
    def list_cameras(self) -> list[dict]: ...
    def get_mjpeg_buffer(self, cam_id: str) -> Optional[MJPEGBuffer]: ...
    def get_status(self) -> dict: ...
```

**Requirements:**
- Each camera runs in its own `multiprocessing.Process` — Python GIL prevents true parallel GPU inference in threads
- Shared event queue via `multiprocessing.Queue` for alerts to reach the API layer
- Camera config persisted to `data/cameras.json` so cameras survive server restarts
- Max 4 cameras recommended for RTX 4050 with YOLO11n (6GB VRAM)

---

## 6. Zone System

### File: `engine/zones/geometry.py`

**Function: `point_in_polygon`**

Ray-casting algorithm for polygon zone detection.

```python
def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """
    Ray-casting algorithm.
    point: (x, y) pixel coordinates
    polygon: list of (x, y) vertices in order
    Returns True if point is inside polygon
    """
```

**Requirements:**
- Use **bottom-center** of bounding box as the test point: `(x1 + (x2-x1)/2, y2)`
- NOT centroid (mid-body) — bottom-center represents feet-on-ground
- Handles edge cases: point on edge, degenerate polygons

**Function: `compute_iou`**
```python
def compute_iou(box1: tuple, box2: tuple) -> float: ...
# box format: (x1, y1, x2, y2)
```

### File: `engine/zones/manager.py`

**Class: `ZoneManager`**

```python
@dataclass
class Zone:
    zone_id: str
    label: str
    cam_id: str
    polygon: list[tuple[float, float]]   # pixel coordinates
    color: str = "#FF0000"               # hex color for dashboard overlay
    active: bool = True

@dataclass  
class ZoneIntrusion:
    zone_id: str
    zone_label: str
    cam_id: str
    track_id: int
    global_id: str

class ZoneManager:
    def __init__(self, zones_file: str): ...
    def check_intrusions(self, tracks: list[Track], cam_id: str) -> list[ZoneIntrusion]: ...
    def get_zones_for_camera(self, cam_id: str) -> list[Zone]: ...
    def reload(self) -> None: ...   # hot-reload zones.json without restart
    def add_zone(self, zone: Zone) -> None: ...
    def remove_zone(self, zone_id: str) -> None: ...
```

**Hot-reload:** Watch `zones.json` for file modification using `watchdog` library. When file changes, reload zones without restarting the pipeline.

### Data format: `data/zones.json`
```json
[
  {
    "zone_id": "zone_uuid_here",
    "label": "Restricted Area",
    "cam_id": "cam_0",
    "polygon": [[100, 200], [400, 200], [400, 450], [100, 450]],
    "color": "#FF0000",
    "active": true
  }
]
```

---

## 7. Alert System

### File: `engine/alerts/manager.py`

**Class: `AlertManager`**

Central dispatch — deduplication, cooldown, and routing to all output channels.

```python
from enum import Enum

class AlertType(str, Enum):
    INTRUSION = "intrusion"
    WEAPON = "weapon"           # highest priority — bypasses cooldown
    LOITERING = "loitering"
    CROWDING = "crowding"
    VIOLENCE = "violence"
    FACE_MATCH = "face_match"   # known person recognized

@dataclass
class Alert:
    alert_id: str               # UUID
    alert_type: AlertType
    cam_id: str
    zone_id: Optional[str]
    track_ids: list[int]
    global_ids: list[str]
    name: Optional[str]         # if face recognized
    confidence: float
    timestamp: datetime
    snapshot_path: Optional[str]
    metadata: dict              # extra data per alert type

class AlertManager:
    def __init__(self, ws_broadcaster, db, snapshot_writer): ...
    def dispatch(self, event, frame: np.ndarray, cam_id: str) -> None: ...
```

**Deduplication key:** `f"{cam_id}:{zone_id}:{track_id}:{alert_type}"`
- Standard cooldown: 60 seconds (from `settings.alert_cooldown_seconds`)
- Weapon alerts: **NO cooldown** — always fire immediately
- Face match alerts: 5 minute cooldown per person per camera

**Dispatch pipeline (all in daemon threads — never block the video loop):**
1. Save JPEG snapshot → `storage/snapshots.py`
2. Write event to DB → `storage/db.py`
3. Push WebSocket message → `api/routers/ws.py`
4. Send email (if enabled) → `alerts/email.py`
5. POST webhook (if enabled) → `alerts/webhook.py`

### File: `engine/alerts/email.py`

```python
async def send_alert_email(alert: Alert, snapshot_path: str) -> None: ...
```

- Use `aiosmtplib` (async SMTP — never blocks event loop)
- Attach JPEG snapshot
- Subject: `[SENTINAL] {alert_type.upper()} — {cam_id} — {timestamp}`
- Body: plain text + snapshot attachment

### File: `engine/alerts/webhook.py`

```python
async def post_webhook(alert: Alert) -> None: ...
```

- Use `httpx.AsyncClient`
- POST JSON payload to `settings.alert_webhook_url`
- Payload: `alert.__dict__` serialized to JSON (datetime → ISO string)
- Timeout: 5 seconds; silent fail on error (log but don't crash pipeline)

---

## 8. Storage Layer

### File: `engine/storage/db.py`

**Phase 1–4:** SQLite via `aiosqlite` (async, zero setup)  
**Phase 5:** PostgreSQL via `asyncpg`

```python
# Public interface (same for both backends)
async def init_db() -> None: ...
async def insert_event(alert: Alert) -> None: ...
async def get_events(
    limit: int = 50,
    offset: int = 0,
    cam_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    since: Optional[datetime] = None
) -> list[dict]: ...
async def get_identities() -> list[dict]: ...
async def upsert_identity(global_id: str, name: str, embedding: bytes) -> None: ...
async def get_stats() -> dict: ...   # event counts, active cameras, etc.
```

### File: `engine/storage/snapshots.py`

```python
def save_snapshot(frame: np.ndarray, cam_id: str, alert_type: str) -> str:
    """
    Saves JPEG to: data/snapshots/{YYYY-MM-DD}/{cam_id}_{alert_type}_{timestamp}.jpg
    Returns the relative file path string.
    Quality: 85 (good balance of size vs quality)
    """
```

- Create date directory if it doesn't exist
- Never block — called from a daemon thread
- Return path relative to project root (stored in DB, served by FastAPI)

---

## 9. FastAPI Backend

### File: `api/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: init DB, load models, restore cameras from cameras.json
    await init_db()
    camera_service.restore_cameras()
    yield
    # shutdown: stop all camera pipelines
    camera_service.stop_all()

app = FastAPI(title="SENTINAL v2", lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://192.168.1.*"],
    allow_methods=["*"], allow_headers=["*"])
```

### API Routes

#### `api/routers/cameras.py`
```
POST   /api/cameras              — add camera {cam_id, url, label}
DELETE /api/cameras/{cam_id}     — remove camera and stop pipeline
GET    /api/cameras              — list all cameras with status
PATCH  /api/cameras/{cam_id}     — update camera (url, label, active)
```

#### `api/routers/stream.py`
```
GET    /api/stream/{cam_id}      — MJPEG stream (multipart/x-mixed-replace)
```
Returns `StreamingResponse` from `MJPEGBuffer.frame_generator()`.

#### `api/routers/events.py`
```
GET    /api/events               — paginated event log
       query params: limit, offset, cam_id, alert_type, since (ISO datetime)
GET    /api/events/{event_id}    — single event detail
GET    /api/snapshots/{path}     — serve snapshot JPEG file
```

#### `api/routers/zones.py`
```
GET    /api/zones                — all zones (optionally filtered by cam_id)
POST   /api/zones                — create zone {label, cam_id, polygon, color}
PUT    /api/zones/{zone_id}      — update zone
DELETE /api/zones/{zone_id}      — delete zone
```
All mutations trigger `zone_manager.reload()`.

#### `api/routers/identities.py`
```
GET    /api/identities           — list all known identities
PUT    /api/identities/{id}      — set name for a global_id
POST   /api/identities/{id}/enroll  — upload face photo to enroll
DELETE /api/identities/{id}      — remove identity
```

#### `api/routers/stats.py`
```
GET    /api/stats                — summary: total events, events today, active cameras,
                                   top alert types, events per camera
```

#### `api/routers/alerts.py`
```
GET    /api/alerts/config        — get current alert config (email, webhook settings)
PUT    /api/alerts/config        — update alert config (enables/disables channels)
POST   /api/alerts/test          — send a test email/webhook to verify config
```

#### `api/routers/ws.py`

WebSocket endpoint for real-time dashboard updates.

```
WS     /ws/live                  — real-time JSON event stream
```

Message format pushed to all connected clients:
```json
{
  "type": "alert",
  "alert_type": "intrusion",
  "cam_id": "cam_0",
  "zone_label": "Restricted Area",
  "global_id": "uuid-here",
  "name": "John Doe",
  "timestamp": "2025-03-06T14:32:00",
  "snapshot_url": "/api/snapshots/2025-03-06/cam_0_intrusion_14320.jpg"
}
```

Weapon alert message (triggers full-screen alarm on dashboard):
```json
{
  "type": "weapon_alarm",
  "cam_id": "cam_0",
  "class_name": "knife",
  "confidence": 0.82,
  "timestamp": "...",
  "snapshot_url": "..."
}
```

---

## 10. React Dashboard

### Tech stack
- React 18 + Vite (TypeScript optional — plain JS is fine)
- shadcn/ui components + Tailwind CSS
- Zustand for global state
- Recharts for analytics charts
- React Router v6 for page routing
- Lucide React for icons

### Pages

#### `LiveView.jsx` — Main surveillance view
- CSS Grid: 1×1, 2×2, or 3×3 layout (user-selectable)
- Each camera card:
  - `<img src="/api/stream/{cam_id}" />` for live MJPEG feed
  - Overlaid canvas showing zone polygons (SVG or Canvas API)
  - Active tracks count badge
  - Camera name + connection status indicator (green/red dot)
- Right sidebar: real-time EventFeed (WebSocket)
- Full-screen `AlertBanner` component when weapon alarm fires (red background, alarm text, dismiss button)

#### `Events.jsx` — Event log
- Paginated table: timestamp, camera, type, zone, person name/ID, snapshot thumbnail
- Filters: by camera, alert type, date range
- Click row → modal with full snapshot + event details
- Export to CSV button

#### `Identities.jsx` — Known persons management
- Grid of person cards: face crop (if enrolled), name, last seen camera + time, total sightings
- Click to edit name
- Upload face photo to enroll
- Delete identity

#### `Zones.jsx` — Zone editor
- Select camera from dropdown → show live feed as background
- Draw polygon zones by clicking points on the feed image
- Edit zone: label, color, active/inactive toggle
- Delete zone
- Changes save immediately and hot-reload in the engine

#### `Alerts.jsx` — Alert configuration
- Toggle email alerts: on/off
- Email settings: SMTP host, port, sender, recipient, password
- Toggle webhook: on/off + URL input
- Test button for each channel
- Alert cooldown slider (default 60s)

#### `Analytics.jsx` — Charts and statistics
- Events over time (line chart, last 24h / 7 days / 30 days)
- Events by camera (bar chart)
- Events by type (pie chart)
- Top active zones
- Active hours heatmap (hour of day × day of week)
- Summary cards: total events, events today, most active camera, most triggered zone

### Global State (Zustand store: `store/useStore.js`)
```javascript
{
  cameras: [],            // list of camera objects
  events: [],             // recent events (last 100)
  identities: [],         // known persons
  zones: [],              // all zones
  weaponAlarm: null,      // non-null when weapon alert is active
  wsConnected: false,     // WebSocket connection status
  gridLayout: '2x2',      // LiveView grid size
}
```

### WebSocket connection (in `store/useStore.js`)
```javascript
const ws = new WebSocket('ws://[server-ip]:8000/ws/live');
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'weapon_alarm') {
    set({ weaponAlarm: msg });
  } else {
    set(state => ({ events: [msg, ...state.events].slice(0, 100) }));
  }
};
// Reconnect with exponential backoff on close
```

### `components/AlertBanner.jsx`
- Full-screen red overlay
- Shows: "⚠️ WEAPON DETECTED — [camera name] — [class_name]"
- Flashing animation (CSS keyframes)
- Snapshot image
- Large "DISMISS" button
- Auto-dismiss after 60 seconds if not manually dismissed
- Plays an audio alert (browser Audio API, short beep)

### `components/ZoneEditor.jsx`
- Displays camera MJPEG feed as background
- Click to add polygon vertex
- Double-click to close polygon
- Drag vertices to adjust
- Color picker for zone color
- Label input
- Save / Cancel buttons

---

## 11. Database Schema

### SQLite (Phase 1–4) / PostgreSQL (Phase 5)

```sql
-- Events: every alert that fired
CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,       -- UUID
    alert_type  TEXT NOT NULL,          -- AlertType enum value
    cam_id      TEXT NOT NULL,
    zone_id     TEXT,
    track_ids   TEXT,                   -- JSON array: [1, 2, 3]
    global_ids  TEXT,                   -- JSON array of UUID strings
    name        TEXT,                   -- face-recognized name if any
    confidence  REAL,
    timestamp   TEXT NOT NULL,          -- ISO 8601
    snapshot_path TEXT,
    metadata    TEXT                    -- JSON object for extra data
);

-- Known identities: enrolled persons
CREATE TABLE IF NOT EXISTS identities (
    global_id   TEXT PRIMARY KEY,       -- UUID (same as Re-ID global_id)
    name        TEXT,                   -- human-assigned name ("John Doe", "Unknown #3")
    embedding   BLOB,                   -- 512-d float32 numpy array, serialized
    enrolled_at TEXT,
    last_seen   TEXT,
    last_cam    TEXT,
    sighting_count INTEGER DEFAULT 0
);

-- Cameras: persisted camera config
CREATE TABLE IF NOT EXISTS cameras (
    cam_id      TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    label       TEXT,
    active      INTEGER DEFAULT 1,
    added_at    TEXT
);

-- Zones: persisted zone definitions (mirrors zones.json)
CREATE TABLE IF NOT EXISTS zones (
    zone_id     TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    cam_id      TEXT NOT NULL,
    polygon     TEXT NOT NULL,          -- JSON array of [x,y] pairs
    color       TEXT DEFAULT '#FF0000',
    active      INTEGER DEFAULT 1
);
```

---

## 12. Docker Deployment

### File: `docker-compose.yml` (Phase 5)

```yaml
version: '3.9'
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: sentinal
      POSTGRES_USER: sentinal
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  engine:
    build: .
    runtime: nvidia           # requires nvidia-container-toolkit
    environment:
      - DB_URL=postgresql+asyncpg://sentinal:${POSTGRES_PASSWORD}@postgres/sentinal
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./models:/app/models
    depends_on: [postgres]
    restart: unless-stopped
    network_mode: host        # needed for camera discovery on local network

  dashboard:
    build: ./dashboard
    ports:
      - "5173:80"
    depends_on: [engine]
    restart: unless-stopped

volumes:
  postgres_data:
```

---

## 13. Requirements & Dependencies

### `requirements.txt` — install phase by phase

```
# Phase 1 — Foundation
ultralytics>=8.3.0          # YOLO11 + BoT-SORT
opencv-python>=4.10.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-multipart
pydantic>=2.0.0
pydantic-settings
python-dotenv
numpy
Pillow
aiofiles
aiosqlite                   # async SQLite (Phase 1-4)

# Phase 2 — Zones & Alerts
watchdog                    # hot-reload zones.json

# Phase 3 — Re-ID & Face
torchreid                   # install from GitHub: pip install git+https://github.com/KaiyangZhou/deep-person-reid.git
faiss-cpu                   # or faiss-gpu if VRAM allows
insightface
onnxruntime-gpu             # InsightFace ONNX inference on CUDA

# Phase 4 — Alerts
aiosmtplib                  # async email
httpx                       # async webhook HTTP client

# Phase 5 — Production
asyncpg                     # async PostgreSQL
psycopg2-binary             # sync PostgreSQL fallback
```

### `.gitignore` entries to add:
```
.env
models/
data/snapshots/
data/sentinal.db
data/cameras.json
__pycache__/
*.pyc
node_modules/
dashboard/dist/
```

---

## 14. Phase Build Order

### Phase 1 — Solid Foundation (Weeks 1–2)
Build in this exact order. Do not skip ahead.

1. `engine/config.py` — Pydantic settings
2. `engine/stream/source.py` — VideoSource with reconnect
3. `engine/vision/detector.py` — YOLO11n detection
4. `engine/vision/tracker.py` — BoT-SORT tracking
5. `engine/stream/mjpeg.py` — MJPEG frame buffer
6. `engine/storage/db.py` — SQLite init + insert_event
7. `engine/storage/snapshots.py` — JPEG snapshot writer
8. `engine/pipeline.py` — single-camera pipeline (person only, no zones yet)
9. `api/main.py` — FastAPI app with lifespan
10. `api/routers/stream.py` — MJPEG streaming endpoint
11. `api/routers/cameras.py` — add/list/remove cameras
12. `api/services/camera_service.py` — MultiCamManager singleton
13. `dashboard/` LiveView.jsx — single camera `<img>` only (no overlays yet)

**Milestone:** Open browser → see live tracked person with bounding box. Stream runs 30 min without dropping.

---

### Phase 2 — Multi-Camera + Zones (Weeks 3–4)

1. `engine/manager.py` — MultiCamManager with multiprocessing
2. `engine/zones/geometry.py` — ray-casting, IoU
3. `engine/zones/manager.py` — ZoneManager with hot-reload
4. `engine/alerts/manager.py` — AlertManager (dedup, cooldown, dispatch)
5. `engine/storage/snapshots.py` — integrate with AlertManager
6. `api/routers/zones.py` — zone CRUD
7. `api/routers/events.py` — event log API
8. `api/routers/ws.py` — WebSocket broadcaster
9. Dashboard: multi-cam grid + zone SVG overlay + EventFeed sidebar

**Milestone:** 3 cameras running, zones drawn, intrusion logged to DB, appears in EventFeed.

---

### Phase 3 — Re-ID + Face Recognition (Weeks 5–6)

1. `engine/vision/reid.py` — OSNet-AIN + FAISS + EMA + TTL pool
2. `engine/vision/face.py` — InsightFace buffalo_l
3. `engine/storage/db.py` — add identities table
4. `api/routers/identities.py` — identity management API
5. Dashboard: Identities page + PersonBadge component + face enrollment UI

**Milestone:** Person enters camera 1, exits, enters camera 2 — same global_id assigned.

---

### Phase 4 — Weapons + Anomaly + Full Alerts (Weeks 7–8)

1. `engine/vision/weapon.py` — weapon class filter
2. `engine/vision/anomaly.py` — loitering, crowding, violence rules
3. `engine/alerts/email.py` — async SMTP
4. `engine/alerts/webhook.py` — async webhook POST
5. `api/routers/alerts.py` — alert config API
6. Dashboard: AlertBanner weapon alarm + Alerts config page + Analytics page

**Milestone:** Show weapon on camera → red banner fires in < 3 seconds → email received.

---

### Phase 5 — Production Polish (Weeks 9–10)

1. Migrate SQLite → PostgreSQL in `engine/storage/db.py`
2. `docker-compose.yml` — full containerized stack
3. `Dockerfile` for engine + `dashboard/Dockerfile` for React build
4. Dashboard: Zones editor (interactive polygon drawing) + Analytics charts
5. JWT auth for dashboard (optional but recommended)
6. Performance test: 4 cameras @ 15fps sustained on RTX 4050

**Milestone:** `docker compose up` on a fresh machine starts the entire system.

---

*End of SPEC.md — last updated for SENTINAL v2 research-verified plan.*
