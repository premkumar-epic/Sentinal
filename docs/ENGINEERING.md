# SENTINAL v2 — Internal Engineering Documentation

> Complete reference guide reverse-engineered from static analysis of the full codebase.
> Generated: 2026-03-13 | Codebase: ~12,100 lines (Python + JS)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture & Design Patterns](#2-architecture--design-patterns)
3. [Module Map & Dependency Graph](#3-module-map--dependency-graph)
4. [Engine Core (`engine/`)](#4-engine-core)
5. [Vision Subsystem (`engine/vision/`)](#5-vision-subsystem)
6. [Zone System (`engine/zones/`)](#6-zone-system)
7. [Alert System (`engine/alerts/`)](#7-alert-system)
8. [Storage Layer (`engine/storage/`)](#8-storage-layer)
9. [Stream Subsystem (`engine/stream/`)](#9-stream-subsystem)
10. [API Layer (`api/`)](#10-api-layer)
11. [Frontend Dashboard (`dashboard/`)](#11-frontend-dashboard)
12. [Authentication & Security](#12-authentication--security)
13. [Configuration System](#13-configuration-system)
14. [System Flow Diagrams](#14-system-flow-diagrams)
15. [Feature-to-Code Mapping](#15-feature-to-code-mapping)
16. [Complete Feature List](#16-complete-feature-list)
17. [Data Model & Schema](#17-data-model--schema)
18. [Deployment](#18-deployment)
19. [File Index](#19-file-index)

---

## 1. System Overview

SENTINAL v2 is a **zero-cloud, on-premise AI video surveillance system**. It processes live camera feeds through a GPU-accelerated AI pipeline that detects people, tracks them across cameras, recognizes faces, detects weapons, identifies behavioral anomalies, and dispatches real-time alerts — all without sending any data to external cloud services.

### Hardware Target

| Role | Machine | Purpose |
|------|---------|---------|
| AI Server | RTX 4050 laptop (CUDA) | Runs all AI models + FastAPI backend |
| Client | Zenbook 14 (Arc 130T) | Browser-only, accesses dashboard over LAN |
| Cameras | Android phones (DroidCam/IP Webcam) | WiFi video sources over HTTP/RTSP |

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Object Detection | YOLOv11l (Ultralytics) | Person + weapon detection, CUDA FP16 |
| Tracking | BoT-SORT (boxmot) | Stable per-camera track IDs |
| Re-Identification | OSNet-AIN x1.0 (torchreid) + FAISS | Cross-camera person matching |
| Face Recognition | InsightFace ArcFace (buffalo_l) | Face detection, embedding, enrollment |
| API | FastAPI (async + WebSocket) | REST + real-time event push |
| Database | SQLite (default) / PostgreSQL (prod) | Event log, identities, zones |
| Frontend | React 18 + Vite + Zustand | Single-page dashboard |
| Video Delivery | MJPEG over HTTP | Browser-native `<img>` streaming |

### Codebase Size

| Directory | Files | Lines | Purpose |
|-----------|-------|-------|---------|
| `engine/` | 25 .py | ~5,800 | AI core, pipeline, vision, storage |
| `api/` | 16 .py | ~1,500 | FastAPI routers, middleware, services |
| `dashboard/src/` | 18 .jsx/.js | ~4,800 | React frontend |
| **Total** | **~59** | **~12,100** | |

---

## 2. Architecture & Design Patterns

### 2.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Dashboard (Vite)                     │
│  Pages: LiveView, Events, Identities, Zones, Alerts, etc.   │
│  State: Zustand store (useStore.js)                          │
│  Transport: REST (fetch) + WebSocket (real-time events)      │
├─────────────────────────────────────────────────────────────┤
│                    FastAPI (api/)                             │
│  Routers: cameras, stream, events, zones, identities,        │
│           alerts, stats, auth, modules, ws                   │
│  Middleware: JWT auth, CORS, rate limiting, request logging   │
│  Services: camera_service (singleton bridge), auth_service    │
├─────────────────────────────────────────────────────────────┤
│                    Engine Core (engine/)                      │
│  CameraPipeline → Detector → Tracker → ReID → Face → Zones  │
│  MultiCamManager orchestrates all pipelines                  │
│  AlertManager dispatches to DB/WS/Email/Webhook/Telegram     │
│  ModuleRegistry manages pluggable detection modules          │
├─────────────────────────────────────────────────────────────┤
│                    Storage (engine/storage/)                  │
│  Abstract base → SQLiteBackend / PostgresBackend             │
│  Facade (db.py) provides unified async API                   │
│  Snapshots written to disk (data/snapshots/)                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Design Patterns Used

| Pattern | Where | Why |
|---------|-------|-----|
| **Singleton** | `_CameraService`, `ZoneManager.get_instance()`, shared singletons in `camera_service.py` | Single ReIDEngine/FaceRecognizer shared across all cameras for cross-camera matching |
| **Facade** | `engine/storage/db.py` | Hides SQLite vs PostgreSQL choice behind unified async API |
| **Strategy** | `DatabaseBackend` ABC with `SQLiteBackend`/`PostgresBackend` | Swap database engine without changing callers |
| **Template Method** | `DetectionModule` ABC (load/unload/process lifecycle) | Pluggable detection modules with uniform interface |
| **Registry** | `ModuleRegistry` | Central management of detection module lifecycle |
| **Observer/Pub-Sub** | WebSocket `ConnectionManager.broadcast()` | Real-time event push to all connected dashboard clients |
| **Producer-Consumer** | `queue.Queue` alert pipeline between camera threads and alert listener | Decouples alert generation from alert dispatch |
| **Builder** | `AlertManager._build_alert_from_event()` | Constructs Alert from duck-typed event objects |
| **EMA (Exponential Moving Average)** | ReID embedding updates, bbox smoothing | Temporal stability for embeddings and visual tracking |
| **Lazy Initialization** | All model loading in `_init_models()`, lazy imports in routers | Fast startup; models load inside worker threads |
| **Hot Reload** | ZoneManager + watchdog file observer | Zone config changes apply without restart |
| **Atomic Write** | `ZoneManager._save_atomic()` via `tempfile.mkstemp` + `os.replace` | Prevents corrupted zone files on crash |

### 2.3 Threading Model

```
Main Thread (uvicorn/asyncio event loop)
  ├── FastAPI request handlers (async)
  ├── WebSocket connections (async)
  └── MJPEGBuffer consumers (async generators)

Per-Camera Threads (daemon)
  ├── VideoSource-{cam_id}     — reads frames from camera
  └── CamThread-{cam_id}       — runs CameraPipeline._run()
        ├── Detector (YOLO inference)
        ├── Tracker (BoT-SORT update)
        ├── ReID (OSNet embedding extraction)
        ├── FaceRecognizer (InsightFace)
        ├── WeaponDetector / ModuleRegistry
        └── ZoneManager.check_intrusions()

Background Threads (daemon)
  ├── AlertQueueListener       — drains shared alert queue
  ├── AlertDisp-{0..3}         — ThreadPoolExecutor for alert I/O
  ├── _register_new_person     — saves identity snapshots + DB writes
  └── face.enroll._persist     — face enrollment DB persistence

Watchdog Thread
  └── ZoneManager Observer     — watches data/zones.json for changes
```

### 2.4 Concurrency Strategy

- **Never block the event loop**: All CPU-intensive work (YOLO, ReID, face detection) runs in daemon threads.
- **Thread-safe state**: `threading.RLock` on all shared mutable state (ReIDEngine gallery, ZoneManager zones, AlertManager cooldowns).
- **Async bridge**: `asyncio.run_coroutine_threadsafe()` schedules coroutines (DB writes, WS broadcasts) from worker threads onto the main event loop.
- **Event-based shutdown**: `threading.Event` for stop signals — no `time.sleep()` in loops.
- **Frame deduplication**: Pipeline checks `id(frame)` to skip already-processed frames.

---

## 3. Module Map & Dependency Graph

### 3.1 Import Dependency Graph

```
engine/config.py (settings)
    ↑ imported by everything

engine/vision/detector.py ← engine/vision/tracker.py
                           ← engine/vision/weapon.py
                           ← engine/vision/modules/base.py

engine/vision/tracker.py   ← engine/vision/anomaly.py
                           ← engine/pipeline.py

engine/vision/reid.py      ← engine/pipeline.py
engine/vision/face.py      ← engine/pipeline.py
engine/vision/anomaly.py   ← engine/vision/modules/anomaly_module.py
engine/vision/weapon.py    ← engine/vision/modules/weapon_module.py

engine/zones/geometry.py   ← engine/zones/manager.py
                           ← engine/vision/anomaly.py

engine/zones/manager.py    ← engine/pipeline.py
                           ← api/routers/zones.py
                           ← api/services/camera_service.py

engine/alerts/manager.py   ← engine/pipeline.py
                           ← api/services/camera_service.py
engine/alerts/email.py     ← engine/alerts/manager.py
engine/alerts/webhook.py   ← engine/alerts/manager.py
engine/alerts/telegram.py  ← engine/alerts/manager.py

engine/storage/base.py     ← engine/storage/sqlite.py
                           ← engine/storage/postgres.py
engine/storage/db.py       ← api/routers/*
                           ← engine/pipeline.py (via camera_service)

engine/stream/source.py    ← engine/pipeline.py
engine/stream/mjpeg.py     ← engine/pipeline.py
                           ← api/routers/stream.py

engine/pipeline.py         ← engine/manager.py
engine/manager.py          ← api/services/camera_service.py
api/services/camera_service.py ← api/main.py (lifespan)
                               ← api/routers/*.py (lazy imports)
```

### 3.2 Circular Import Avoidance

The codebase uses **lazy imports** (inside functions, not at module level) in several locations to break circular dependencies:

- `api/main.py` imports routers at module bottom (after `app` is created)
- All API routers import `camera_service` inside endpoint functions
- `engine/pipeline.py` lazily imports ReIDEngine, FaceRecognizer, WeaponDetector, ZoneManager inside `_init_models()`
- `engine/alerts/manager.py` lazily imports `email`, `webhook`, `telegram` inside `_dispatch_async_handlers()`

---

## 4. Engine Core

### 4.1 `engine/config.py` — Configuration System (121 lines)

**Purpose**: Single source of truth for all runtime settings.

**Class**: `Settings(BaseSettings)` — Pydantic BaseSettings loads from `.env` file.

**Why it exists**: Prevents hardcoded values anywhere in the codebase. Every tunable parameter (thresholds, paths, ports, model names) is configured here.

| Setting Group | Key Settings | Default |
|---------------|-------------|---------|
| Server | `api_host`, `api_port`, `cors_origins` | `0.0.0.0:8000` |
| Models | `yolo_model`, `reid_model`, `face_model` | `yolo11l.pt`, OSNet-AIN, `buffalo_l` |
| Thresholds | `yolo_conf`, `reid_threshold`, `face_match_threshold` | 0.45, 0.62, 0.68 |
| Performance | `pipeline_process_every_n`, `yolo_imgsz` | 3, 480 |
| Auth | `auth_username`, `auth_password_hash`, `jwt_secret_key` | admin/sentinal, auto-generated |
| Alerts | Email, Webhook, Telegram configs | All disabled |
| Modules | `module_weapon_enabled`, `module_ppe_enabled`, `module_anomaly_enabled` | weapon+anomaly on, PPE off |

**Special behavior**: `jwt_secret_key` validator auto-generates a random 64-byte key if the default `"change-me-in-production"` is detected, with a warning log.

**Singleton**: `settings = Settings()` is created at module level and imported everywhere.

---

### 4.2 `engine/pipeline.py` — CameraPipeline (827 lines)

**Purpose**: The core AI processing loop for a single camera feed. This is the largest and most complex file in the codebase.

**Why it exists**: Orchestrates the entire detection → tracking → identification → alerting chain per camera. Each camera gets its own CameraPipeline running in a dedicated daemon thread.

#### Class: `CameraPipeline`

**Constructor** accepts all shared singletons (zone_manager, alert_manager, reid_engine, face_recognizer, weapon_detector, anomaly_detector, module_registry) so that cross-camera state is shared.

**Lifecycle**:
```
__init__() → start() → _run() → [loop] → stop()
                          ↓
                    _init_models()  (lazy model loading)
                          ↓
              ┌─── run_ai? ────────────────────────┐
              │ YES: _process_frame_ai()           │ NO: reuse cached results
              │   1. _detector.detect(frame)       │
              │   2. _tracker.update(dets, frame)  │
              │   3. _smooth_bboxes(tracks)        │
              │   4. _process_identities()         │
              │   5. _handle_lost_tracks()         │
              │   6. _periodic_maintenance()       │
              │   7. _check_weapons()              │
              │   8. _process_zones()              │
              │   9. _process_modules()            │
              └────────────────────────────────────┘
                          ↓
              _annotate_and_push() → MJPEGBuffer
```

**Frame Skip Logic**: AI runs every Nth frame (`pipeline_process_every_n`, default 3). ReID runs every Nth AI frame (`pipeline_reid_every_n`, default 3). Face runs every Nth AI frame (`pipeline_face_every_n`, default 5). Non-AI frames reuse cached results.

**Identity Registration Flow**:
1. Track stability check: person must maintain same global_id for `_STABILITY_FRAMES` (10) consecutive frames
2. Best crop selection: keeps highest-quality crop (area * visibility_ratio)
3. `_register_new_person()` spawns a daemon thread to:
   - Save reference snapshot to `data/snapshots/identities/{gid}.jpg`
   - Persist to DB via `upsert_identity()`
   - Dispatch `IDENTITY_REGISTERED` alert via AlertManager

**BBox Smoothing**: EMA with `_SMOOTHING_ALPHA = 0.45` reduces jitter in bounding box positions.

**Alert Routing**: Alerts are pushed to either `self._alert_queue` (when running in MultiCamManager with shared queue) or directly to `self._alert_manager.dispatch()`.

#### Function: `_draw_annotations()` (top-level, ~130 lines)

Renders the annotated frame with:
- Zone polygons (semi-transparent fill + outline, red when triggered)
- Person bounding boxes (green) with ID labels (`name` > `global_id[:6]` > `track_id`)
- Weapon bounding boxes (color-coded by threat level: red/orange/yellow)
- Module detections (PPE violations, etc.)
- Weapon-to-person association lines
- Resolution-scaled annotation sizing

#### Class: `_FPSCounter`

Rolling FPS counter using a deque of 30 timestamps.

---

### 4.3 `engine/manager.py` — MultiCamManager (190 lines)

**Purpose**: Orchestrates all CameraPipeline instances.

**Why it exists**: Provides a centralized API for adding/removing/listing cameras and handles persistence to `data/cameras.json`.

**Key Design Decisions**:
- Uses daemon **threads** (not multiprocessing) for Windows compatibility
- Shared `queue.Queue` for alerts from all camera threads
- Camera limit: `_MAX_CAMERAS = 4` (configurable)
- Camera state persisted to JSON on every add/remove

**Alert Listener**: A dedicated background thread drains the shared alert queue and routes items to `AlertManager.dispatch()`.

**Camera Restore**: On startup, reads `data/cameras.json` and re-starts all previously registered cameras. Supports a callback (`add_camera_fn`) so `_CameraService` can inject shared singletons.

---

### 4.4 `engine/launcher.py` — Process Launcher (29 lines)

**Purpose**: Isolated entry point for launching camera pipelines as separate processes.

**Why it exists**: Avoids pickle issues when using `multiprocessing`. Imports `CameraPipeline` inside the function body, not at module level.

**Status**: Currently unused — the system uses threads (`MultiCamManager`) instead of processes.

---

## 5. Vision Subsystem

### 5.1 `engine/vision/detector.py` — YOLO Detector (191 lines)

**Purpose**: Wraps Ultralytics YOLO for person and weapon detection.

**Class**: `Detector`

**Why it exists**: Abstracts YOLO inference behind a clean `detect(frame) → list[Detection]` API. Handles preprocessing, class-specific confidence thresholds, and geometry filtering.

**Detection Dataclass**:
```python
@dataclass
class Detection:
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    class_name: str
```

**Preprocessing**: Adaptive CLAHE applied only in low-light conditions (mean brightness < 100 or std < 40). This avoids unnecessary computation on well-lit frames.

**Filtering Pipeline**:
1. Class filter: Only persons (class_id=0) and weapons (keyword match against `_WEAPON_KEYWORDS`)
2. Class-specific confidence: persons ≥ 0.45, weapons ≥ 0.55
3. Minimum size: 32×32 pixels
4. Aspect ratio: 0.2–5.0 (rejects anomalous shapes)
5. Edge clipping: rejects boxes >70% clipped by frame edge

**Performance**: FP16 inference on CUDA (`half=True`), configurable input resolution (`yolo_imgsz`, default 480).

---

### 5.2 `engine/vision/tracker.py` — BoT-SORT Tracker (125 lines)

**Purpose**: Assigns stable per-camera track IDs to detected persons across frames.

**Class**: `Tracker`

**Why it exists**: Raw detections have no temporal identity. BoT-SORT uses appearance and motion cues to maintain stable IDs as people move.

**Track Dataclass**:
```python
@dataclass
class Track:
    track_id: int
    bbox: tuple[int, int, int, int]
    confidence: float
    global_id: Optional[str] = None  # Set later by ReID
```

**Backend Strategy**:
- Primary: `boxmot.BotSort` with `with_reid=False` (uses SENTINAL's own ReID engine)
- Fallback: Sequential ID assignment per frame (only if boxmot unavailable — IDs not stable)

**Empty Frame Handling**: When no persons detected, `tracker.update()` is still called with empty input to maintain internal state.

---

### 5.3 `engine/vision/reid.py` — ReID Engine (611 lines)

**Purpose**: Cross-camera person re-identification using deep feature embeddings.

**Class**: `ReIDEngine`

**Why it exists**: Track IDs are local to one camera. ReID matches the same person across different cameras and across time (re-entry) using appearance similarity.

**Model**: OSNet-AIN x1.0 (torchreid), pretrained on MSMT17. Falls back to ResNet50 (ImageNet) if torchreid unavailable. Falls back to random embeddings if both fail.

**Core Data Structures** (all protected by `threading.RLock`):
| Structure | Type | Purpose |
|-----------|------|---------|
| `gallery` | `faiss.IndexFlatIP(512)` | FAISS inner-product index for fast similarity search |
| `id_map` | `{faiss_idx: global_id}` | Maps FAISS row index to identity UUID |
| `shot_store` | `{global_id: [emb1, emb2, ...]}` | Multi-shot gallery (up to 12 embeddings per person) |
| `local_to_global` | `{(cam_id, track_id): global_id}` | Maps camera-local tracks to global identities |
| `lost_pool` | `{global_id: (embedding, expiry)}` | Recently-lost identities for quick re-match (90s TTL) |
| `_gallery_timestamps` | `{global_id: last_seen_time}` | For gallery TTL eviction (15min for transients, never for DB-persisted) |
| `_face_confirmed` | `set[global_id]` | Identities confirmed by face recognition get lower match threshold |

**Matching Algorithm** (`get_or_create_global_id`):
```
1. Zero embedding check → return cached stable UUID
2. Already mapped in local_to_global → EMA update → return existing gid
3. Search lost_pool → if match > MATCH_THRESHOLD → reclaim identity
4. Rebuild FAISS if dirty → search gallery (top-20)
5. Aggregate per-GID scores (best shot) → margin check
6. Face-confirmed identities get threshold lowered by 0.15
7. No match → create new UUID, add to gallery
```

**Multi-Shot Gallery Strategy**:
- `shots[0]` = EMA-smoothed "centroid" embedding (slow blend, α=0.85)
- `shots[1:]` = diverse viewpoint samples (only added if max_similarity < 0.85 to existing shots)
- When full (12 shots), replaces the most redundant shot (highest similarity) to maximize viewpoint diversity

**Merge System**:
- `merge_identities(keep_gid, merge_gid)`: Transfers all embeddings, local mappings, DB-saved status
- `merge_duplicates()`: Periodic scan (every 50 AI frames) merges gallery entries exceeding MATCH_THRESHOLD
- Face-ReID fusion: When face recognition identifies a person, `merge_identities(face_gid, reid_gid)` fuses the two

**Embedding Extraction**:
- CLAHE preprocessing on LAB L-channel
- Resize to 128×256 (OSNet input)
- Horizontal flip augmentation: average original + flipped embeddings for left/right invariance
- L2 normalization
- Quality score: 40% size + 60% Laplacian sharpness

---

### 5.4 `engine/vision/face.py` — Face Recognition (315 lines)

**Purpose**: Face detection, recognition, and enrollment using InsightFace ArcFace.

**Class**: `FaceRecognizer`

**Why it exists**: ReID uses body appearance which can be ambiguous. Face recognition provides high-confidence identity confirmation that anchors ReID matches.

**FaceResult Dataclass**:
```python
@dataclass
class FaceResult:
    bbox: tuple[int, int, int, int]
    embedding: np.ndarray  # 512-d ArcFace
    quality_score: float   # InsightFace det_score
    name: Optional[str]
    global_id: Optional[str]
```

**Analysis Pipeline** (`analyze(frame)`):
1. CLAHE preprocessing on full frame
2. InsightFace face detection
3. Quality gate: area ≥ 2500px, det_score ≥ 0.6, not clipped by frame edge
4. Extract 512-d normalized embedding
5. Match against `known_embeddings` by cosine similarity (best match, not first)
6. Threshold: `face_match_threshold` (default 0.68)

**Enrollment** (`enroll(name, face_image, global_id)`):
1. Detect faces in image
2. Select highest-quality face
3. Extract and store embedding in memory
4. Spawn daemon thread to persist to DB and save snapshot

**Thread Safety**: `threading.RLock` protects `known_embeddings` dict.

**Graceful Degradation**: If `insightface` not installed, `self._app = None` and all methods return empty results.

---

### 5.5 `engine/vision/weapon.py` — Weapon Detector (256 lines)

**Purpose**: Filters YOLO detections for weapon classes, associates with nearest person, classifies threat level.

**Class**: `WeaponDetector`

**Why it exists**: Weapons require special handling: threat classification, person association, temporal confirmation, and bypassing alert cooldowns.

**Threat Classification**:
| Level | Keywords | Severity |
|-------|----------|----------|
| CRITICAL | gun, pistol, rifle, firearm, handgun, shotgun, revolver | Immediate lockdown |
| HIGH | knife, sword, machete, dagger, blade, axe | Serious harm |
| MEDIUM | baseball bat, bat, rod, stick, club, hammer, scissors | Potential harm |

**Temporal Confirmation**: Requires 2 detections in last 5 frames to confirm (reduces single-frame false positives).

**Person Association Strategy**:
1. Overlap check: weapon center inside person bbox (with 10% expansion)
2. Fallback: nearest person by Euclidean distance (max 300px)

**WeaponAlert Dataclass**: Includes `threat_level`, `holder_track_id`, `holder_global_id`.

---

### 5.6 `engine/vision/anomaly.py` — Anomaly Detector (251 lines)

**Purpose**: Rule-based behavioral anomaly detection (no ML model required).

**Class**: `AnomalyDetector`

**Why it exists**: Detects suspicious behavioral patterns that object detection alone cannot identify.

**Anomaly Types**:

| Type | Detection Method | Threshold |
|------|------------------|-----------|
| **Loitering** | Same track in same zone for extended period | `loitering_seconds` (30s) |
| **Crowding** | Zone person count exceeds threshold | `crowd_threshold` (5 people) |
| **Violence** | Kinematic analysis of pair interactions | Velocity + proximity + IoU |

**Violence Detection Algorithm**:
1. For each pair of tracks, compute:
   - **Normalized distance**: center-to-center / average height
   - **Normalized velocity**: movement magnitude / height / time delta
   - **IoU**: bounding box overlap
2. Pair is flagged if: (proximal OR touching) AND moving rapidly
3. Requires sustained interaction (>1.5 seconds) before firing
4. Per-pair cooldown prevents duplicate alerts

---

### 5.7 Module System (`engine/vision/modules/`)

**Purpose**: Pluggable detection module framework with lifecycle management.

#### `base.py` — Abstract Base (104 lines)

Defines the module contract:

```python
class DetectionModule(ABC):
    module_id: str          # "weapon", "ppe", "anomaly"
    display_name: str       # "Weapon Detection"
    requires_model: bool    # True if needs a model file

    load() → None           # Initialize resources
    unload() → None         # Free resources (VRAM)
    process(FrameContext) → ModuleResult  # Run detection
```

**FrameContext**: Bundles frame + detections + tracks + global_ids + cam_id + zone_events into one object passed to every module.

**ModuleResult**: Contains `alerts` (dispatched to AlertManager) and `detections` (drawn as annotations).

#### `registry.py` — ModuleRegistry (179 lines)

Central lifecycle manager:
- Register modules at startup
- Enable/disable with model load/unload
- Persist enabled state to `data/modules.json`
- Thread-safe `get_enabled_modules()` for pipeline iteration
- Frees CUDA VRAM on disable via `torch.cuda.empty_cache()`

#### `weapon_module.py` — WeaponModule (211 lines)

Dual-mode weapon detection:
1. **Dedicated model**: `yolov8s_weapons.pt` — separate YOLO inference
2. **COCO fallback**: Filters main YOLO detections using `WeaponDetector`

Falls back automatically if dedicated model file doesn't exist.

#### `ppe_module.py` — PPEModule (218 lines)

PPE compliance checking:
1. Runs dedicated YOLO model on frame to detect PPE items (helmet, vest, gloves, goggles, boots)
2. Associates each PPE item with nearest person track
3. Checks required items against detected items
4. Generates violation alerts for missing PPE

#### `anomaly_module.py` — AnomalyModule (62 lines)

Thin wrapper around `AnomalyDetector`. No model needed — purely rule-based.

---

## 6. Zone System

### 6.1 `engine/zones/geometry.py` — Geometry Engine (134 lines)

**Purpose**: Mathematical primitives for zone intersection testing.

**`point_in_polygon(point, polygon)`**: Ray-casting algorithm. Casts a ray from the test point rightward and counts edge crossings. Odd = inside.

**Design Decision**: Uses the **bottom-center** of the bounding box as the test point, not the centroid. This represents feet-on-ground, which is more accurate for standing persons.

**`compute_iou(box1, box2)`**: Standard Intersection over Union for bounding box overlap, used by the violence detection algorithm.

### 6.2 `engine/zones/manager.py` — ZoneManager (242 lines)

**Purpose**: Manages virtual detection zones and performs real-time intrusion detection.

**Why it exists**: Allows operators to define restricted areas in camera views where person presence triggers alerts.

**Zone Dataclass**:
```python
@dataclass
class Zone:
    zone_id: str
    label: str
    cam_id: str
    polygon: List[Tuple[float, float]]
    color: str = '#FF0000'
    active: bool = True
```

**Singleton Pattern**: `ZoneManager.get_instance()` ensures pipeline threads and API routers share the same instance.

**Hot Reload**: Uses `watchdog` file observer on `data/zones.json`. Any modification triggers `reload()` — zones update in real-time without server restart.

**Atomic Write**: `_save_atomic()` writes to a temp file then atomically renames it, preventing corruption on crash.

**Intrusion Detection** (`check_intrusions(tracks, cam_id)`):
1. Filter zones to active zones for this camera
2. For each track, compute bottom-center point
3. Test point against each zone polygon using ray-casting
4. Return `ZoneIntrusion` events for all matches

---

## 7. Alert System

### 7.1 `engine/alerts/manager.py` — AlertManager (358 lines)

**Purpose**: Central alert dispatcher with deduplication, cooldown, and multi-channel delivery.

**Why it exists**: Prevents alert fatigue through cooldown logic while ensuring critical alerts (weapons) are never suppressed.

**Alert Dataclass**:
```python
@dataclass
class Alert:
    alert_id: str           # UUID
    alert_type: AlertType   # intrusion, weapon, loitering, crowding, violence, face_match, identity_registered
    cam_id: str
    zone_id: Optional[str]
    track_ids: list[int]
    global_ids: list[str]
    name: Optional[str]
    confidence: float
    timestamp: datetime
    snapshot_path: Optional[str]
    metadata: dict
```

**Cooldown Rules**:
| Alert Type | Cooldown | Key |
|------------|----------|-----|
| Weapon | **None** (bypass all cooldowns) | — |
| Face Match | 300 seconds | `{cam_id}:{global_id}:face_match` |
| All others | 60 seconds | `{cam_id}:{zone_id}:{track_id}:{alert_type}` |

**Dispatch Pipeline** (runs in ThreadPoolExecutor with 4 workers):
```
1. Save JPEG snapshot to disk
2. Insert alert into database
3. Push WebSocket message to all connected dashboards
4. Send email (if enabled)
5. POST to webhook (if enabled)
6. Send Telegram message (if enabled)
```

**Thread Safety**: Cooldown dict protected by `threading.RLock`, pruned when >500 entries.

### 7.2 `engine/alerts/email.py` — Email Sender (117 lines)

Async SMTP via `aiosmtplib`. Builds MIME multipart message with alert details + optional JPEG attachment.

### 7.3 `engine/alerts/webhook.py` — Webhook Sender (102 lines)

Async HTTP POST via `httpx`. Serializes Alert to JSON with proper datetime/enum conversion.

### 7.4 `engine/alerts/telegram.py` — Telegram Sender (148 lines)

Sends MarkdownV2-formatted messages via Telegram Bot API. Sends photo with caption if snapshot exists, text-only otherwise. Includes severity-specific emoji icons.

---

## 8. Storage Layer

### 8.1 Architecture

```
api/routers/*.py
       ↓ (calls)
engine/storage/db.py          ← Facade (async functions)
       ↓ (delegates to)
engine/storage/base.py        ← ABC (DatabaseBackend)
       ↓ (implemented by)
engine/storage/sqlite.py      ← SQLiteBackend (aiosqlite)
engine/storage/postgres.py    ← PostgresBackend (asyncpg)
```

### 8.2 `engine/storage/base.py` — Abstract Backend (100 lines)

Defines 15 abstract methods covering:
- Event CRUD: `insert_event`, `get_events`, `get_event_by_id`, `delete_all_events`
- Identity CRUD: `get_identities`, `upsert_identity`, `update_identity_name`, `delete_identity`
- Zone CRUD: `get_zones`, `get_zone_by_id`, `upsert_zone`, `delete_zone`
- Stats: `get_stats`, `get_detailed_stats`

### 8.3 `engine/storage/sqlite.py` — SQLite Backend (335 lines)

- Uses `aiosqlite` for async SQLite access
- WAL journal mode + `synchronous=NORMAL` for performance
- `asyncio.Lock` for write serialization
- Creates 4 tables: `events`, `identities`, `cameras`, `zones`

### 8.4 `engine/storage/postgres.py` — PostgreSQL Backend (345 lines)

- Uses `asyncpg` connection pool (2–10 connections)
- Parameterized queries with `$1, $2...` syntax
- Same schema as SQLite but with `BYTEA` for embeddings
- `ON CONFLICT` upsert for idempotent writes

### 8.5 `engine/storage/db.py` — Facade (118 lines)

Module-level singleton `_backend`. Auto-selects SQLite or PostgreSQL based on `settings.db_url`. Exposes simple async functions that delegate to the backend.

### 8.6 `engine/storage/snapshots.py` — Snapshot Writer (45 lines)

Writes JPEG snapshots to `data/snapshots/{YYYY-MM-DD}/{cam_id}_{alert_type}_{timestamp}.jpg`. Quality 85.

### 8.7 Database Schema

```sql
events (
    id            TEXT PRIMARY KEY,   -- UUID
    alert_type    TEXT NOT NULL,      -- "intrusion", "weapon", etc.
    cam_id        TEXT NOT NULL,
    zone_id       TEXT,
    track_ids     TEXT,               -- JSON array
    global_ids    TEXT,               -- JSON array
    name          TEXT,
    confidence    REAL,
    timestamp     TEXT NOT NULL,      -- ISO 8601
    snapshot_path TEXT,
    metadata      TEXT                -- JSON object
)

identities (
    global_id      TEXT PRIMARY KEY,  -- UUID
    name           TEXT,
    embedding      BLOB/BYTEA,        -- 512 × float32 = 2048 bytes
    enrolled_at    TEXT,
    last_seen      TEXT,
    last_cam       TEXT,
    sighting_count INTEGER DEFAULT 0
)

cameras (
    cam_id   TEXT PRIMARY KEY,
    url      TEXT NOT NULL,
    label    TEXT,
    active   INTEGER DEFAULT 1,
    added_at TEXT
)

zones (
    zone_id TEXT PRIMARY KEY,
    label   TEXT NOT NULL,
    cam_id  TEXT NOT NULL,
    polygon TEXT NOT NULL,            -- JSON array of [x,y] pairs
    color   TEXT DEFAULT '#FF0000',
    active  INTEGER DEFAULT 1
)
```

---

## 9. Stream Subsystem

### 9.1 `engine/stream/source.py` — VideoSource (180 lines)

**Purpose**: Threaded camera stream reader with auto-reconnect.

**Why it exists**: OpenCV's `VideoCapture.read()` is blocking. Running it in a background thread ensures the pipeline never stalls waiting for a frame.

**Design**:
- Stores only the **latest 2 frames** (`deque(maxlen=2)`) — never accumulates lag
- `CAP_PROP_BUFFERSIZE = 1` — **mandatory** to prevent frames being 2–5 seconds old
- Auto-reconnect with exponential backoff: 2s → 4s → 8s → 16s → 32s
- RTSP: explicit FFMPEG backend, TCP transport, `grab()` to drain decoder buffer
- Local cameras: tries `CAP_ANY` → `CAP_MSMF` → `CAP_DSHOW`
- `threading.Event` for interruptible sleep — `stop()` takes effect immediately

### 9.2 `engine/stream/mjpeg.py` — MJPEGBuffer (88 lines)

**Purpose**: Bridge between sync pipeline threads and async FastAPI streaming.

**Design**:
- **Push side** (sync, pipeline thread): `push_frame(frame)` → JPEG encode → `call_soon_threadsafe()` into asyncio queue
- **Pull side** (async, FastAPI): `frame_generator()` yields multipart MJPEG chunks
- Queue maxsize=2 with drop-oldest-on-full strategy — never blocks producer
- Browser consumes via `<img src="/api/stream/{cam_id}?token=JWT">`

---

## 10. API Layer

### 10.1 `api/main.py` — Application Entry Point (190 lines)

**Lifespan** (startup/shutdown):
```
Startup:
  1. Create required directories (models, snapshots, zones, logs)
  2. Capture asyncio event loop for thread-safe coroutine scheduling
  3. Initialize database (create tables)
  4. Load known identities into ReID engine + FaceRecognizer
  5. Restore cameras from data/cameras.json
  6. Load startup cameras from STARTUP_CAMERAS env var
  7. Start alert listener thread

Shutdown:
  1. Stop all camera pipelines
  2. Shut down AlertManager executor
  3. Stop ZoneManager watchdog
```

**Middleware Stack**:
1. Request logging (method, path, status, latency — no query params to avoid JWT leaks)
2. CORS (restricted origins, methods, headers)
3. Rate limiting (slowapi)

**Router Registration**: 31 routes total across 10 routers. Auth router is unprotected; most others require JWT. Stream and WebSocket use query-param tokens.

### 10.2 API Routers

#### `cameras.py` — Camera Management (124 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/cameras` | POST | JWT | Add camera + start pipeline |
| `/api/cameras` | GET | JWT | List all cameras with status |
| `/api/cameras/{cam_id}` | DELETE | JWT | Stop + remove camera |
| `/api/cameras/{cam_id}` | PATCH | JWT | Update label/URL/active |

URL validation prevents SSRF: only `rtsp://`, `http://`, `https://`, or numeric device indices allowed.

#### `stream.py` — MJPEG Stream (40 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/stream/{cam_id}` | GET | Query token | Stream MJPEG frames |

Returns `StreamingResponse` with `multipart/x-mixed-replace` content type.

#### `events.py` — Event Log (106 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/events` | GET | JWT | Paginated event list (filter by cam, type, since) |
| `/api/events` | DELETE | JWT | Clear all events |
| `/api/events/{event_id}` | GET | JWT | Single event by ID |
| `/api/snapshots/{path}` | GET | Query token | Serve snapshot JPEG |

**Security**: Snapshot endpoint validates path stays within `snapshots_dir` (path traversal prevention) and allows only `.jpg`/`.jpeg`/`.png`.

#### `zones.py` — Zone CRUD (146 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/zones` | GET | JWT | List zones (optional cam_id filter) |
| `/api/zones` | POST | JWT | Create zone |
| `/api/zones/{zone_id}` | PUT | JWT | Update zone |
| `/api/zones/{zone_id}` | DELETE | JWT | Delete zone |

All mutations write to both the database AND `data/zones.json`, then hot-reload ZoneManager.

#### `identities.py` — Identity Management (125 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/identities` | GET | JWT | List all identities |
| `/api/identities/{global_id}` | PUT | JWT | Update name |
| `/api/identities/{global_id}/enroll` | POST | JWT | Enroll face from uploaded image |
| `/api/identities/{global_id}` | DELETE | JWT | Delete identity + snapshot |

Name updates propagate to the in-memory FaceRecognizer so live preview reflects changes immediately.

#### `alerts.py` — Alert Configuration (246 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/alerts/config` | GET | JWT | Get alert config (passwords masked) |
| `/api/alerts/config` | PUT | JWT | Update alert settings |
| `/api/alerts/test` | POST | JWT | Test all alert channels |

#### `modules.py` — Module Management (81 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/modules` | GET | JWT | List all modules + status |
| `/api/modules/{module_id}` | GET | JWT | Module details |
| `/api/modules/{module_id}` | PUT | JWT | Enable/disable/configure module |

#### `stats.py` — Analytics (85 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/stats` | GET | JWT | System-wide statistics |

Returns: total_events, events_today, active_cameras, events_by_type, events_by_camera, top_zones.

#### `auth.py` — Authentication (48 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/auth/login` | POST | None | Username/password → JWT token |

Rate-limited to 5 requests/minute per IP.

#### `ws.py` — WebSocket (100 lines)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/ws/live` | WS | Query token | Real-time event stream |

`ConnectionManager` manages active connections with async lock. JWT validated before accept. `broadcast_event()` is called by AlertManager from worker threads via `run_coroutine_threadsafe()`.

### 10.3 `api/services/camera_service.py` — Service Layer (273 lines)

**Purpose**: Singleton bridge between API routers and the engine.

**Why it exists**: Ensures all cameras share the same model instances (ReIDEngine, FaceRecognizer, ZoneManager, AlertManager, ModuleRegistry). Without shared singletons, cross-camera Re-ID would fail.

**Lazy Singleton Initialization**: Each getter (`_get_reid_engine()`, `_get_face_recognizer()`, etc.) creates the instance on first call, protected by `threading.Lock`.

**Event Loop Capture**: `set_event_loop()` stores the asyncio event loop during startup so worker threads can schedule coroutines.

### 10.4 `api/middleware/auth.py` — JWT Middleware (67 lines)

Two auth dependencies:
- `get_current_user(token)`: Extracts JWT from `Authorization: Bearer` header
- `get_current_user_from_query(token)`: Extracts JWT from `?token=` query param (for `<img>` and WebSocket)

### 10.5 `api/services/auth_service.py` — Password Hashing (16 lines)

`bcrypt.checkpw()` and `bcrypt.hashpw()` wrappers.

### 10.6 `api/limiter.py` — Rate Limiter (6 lines)

Shared `slowapi.Limiter` instance keyed by remote IP address.

---

## 11. Frontend Dashboard

### 11.1 Architecture

```
React 18 + Vite + Zustand (state management)
No TypeScript — plain JavaScript (.jsx)
No component library — custom CSS
```

### 11.2 State Management — `useStore.js` (401 lines)

Single Zustand store managing:
- **Auth**: `token`, `login()`, `logout()`
- **Data**: `cameras`, `events`, `identities`, `zones`, `modules`
- **Real-time**: WebSocket connection with auto-reconnect (exponential backoff 1s → 30s)
- **UI**: `theme` (dark/light), `gridLayout`, `weaponAlarm`, `toasts`
- **API calls**: 20+ async actions wrapping `fetch()` with Bearer token injection

**WebSocket Handler**: Parses JSON messages and:
- `weapon_alarm` → sets `weaponAlarm` state (triggers AlertBanner)
- `alert` → prepends to `events` array (capped at 100) + fires toast notification

### 11.3 Pages

| Page | File | Lines | Purpose |
|------|------|-------|---------|
| `Login.jsx` | Login form | 233 | Username/password authentication |
| `LiveView.jsx` | Camera grid | 422 | MJPEG streams + real-time overlay |
| `Cameras.jsx` | Camera CRUD | 332 | Add/remove/edit cameras |
| `Events.jsx` | Event log | 442 | Paginated, filterable event table |
| `Identities.jsx` | Identity mgmt | 317 | View/rename/enroll/delete identities |
| `Zones.jsx` | Zone editor | 298 | Create/edit/delete detection zones |
| `Alerts.jsx` | Alert config | 431 | Email/webhook/Telegram settings |
| `Analytics.jsx` | Statistics | 262 | Charts and metrics dashboard |
| `Modules.jsx` | Module control | 205 | Enable/disable detection modules |

### 11.4 Components

| Component | Lines | Purpose |
|-----------|-------|---------|
| `AlertBanner.jsx` | 209 | Full-screen weapon alarm overlay with audio |
| `ToastStack.jsx` | 133 | Stacking notification toasts (auto-dismiss) |
| `ZoneEditor.jsx` | 283 | Interactive polygon drawing on camera image |
| `ZoneOverlay.jsx` | 79 | SVG zone polygon visualization |
| `PersonBadge.jsx` | 39 | Identity avatar/name display chip |

---

## 12. Authentication & Security

### 12.1 Authentication Flow

```
Client                          Server
  │                               │
  ├── POST /api/auth/login ──────►│ Rate-limited: 5/min per IP
  │   {username, password}        │ bcrypt.checkpw(password, hash)
  │                               │ Generate JWT (HS256, 24h expiry)
  │◄── {access_token, bearer} ───┤
  │                               │
  ├── GET /api/cameras ──────────►│ Authorization: Bearer {JWT}
  │   Bearer JWT                  │ Decode + validate + extract "sub"
  │◄── [cameras] ────────────────┤
  │                               │
  ├── GET /api/stream/cam_0 ─────►│ ?token={JWT} (query param)
  │   (browser <img> tag)         │ Same validation, different extraction
  │◄── MJPEG stream ─────────────┤
  │                               │
  ├── WS /ws/live?token={JWT} ───►│ Validate before accept
  │◄── Real-time events ─────────┤
```

### 12.2 Security Measures

| Measure | Implementation |
|---------|----------------|
| Password hashing | bcrypt with random salt |
| JWT signing | HS256, auto-generated secret if default |
| Rate limiting | 5/min on login endpoint (slowapi) |
| CORS | Restricted origins, methods, headers |
| Path traversal prevention | Snapshot endpoint resolves + boundary-checks paths |
| URL validation | Camera URL must be rtsp/http/https or numeric device |
| Request logging | Query params excluded (JWT leak prevention) |
| Sensitive field masking | Alert config API masks passwords/tokens as "***" |
| Token-based WS auth | JWT validated before WebSocket accept |

---

## 13. Configuration System

### 13.1 Configuration Sources

| Source | Purpose | Format |
|--------|---------|--------|
| `.env` | All runtime settings | Key=Value |
| `data/cameras.json` | Persisted camera registry | JSON array |
| `data/zones.json` | Zone polygon definitions | JSON array |
| `data/modules.json` | Module enabled state + config | JSON object |
| `engine/config.py` | Default values, validation | Python (Pydantic) |

### 13.2 Environment Variables (Complete List)

```
# Server
API_HOST, API_PORT, CORS_ORIGINS

# Auth
AUTH_USERNAME, AUTH_PASSWORD_HASH, JWT_SECRET_KEY, JWT_EXPIRE_MINUTES

# Models
YOLO_MODEL, YOLO_CONF, YOLO_IOU, REID_MODEL, REID_THRESHOLD
FACE_MODEL, FACE_QUALITY_THRESHOLD, FACE_MATCH_THRESHOLD, TRACKER_DEVICE

# Paths
MODELS_DIR, SNAPSHOTS_DIR, ZONES_FILE, LOGS_DIR

# Database
DB_URL

# Performance
PIPELINE_PROCESS_EVERY_N, PIPELINE_REID_EVERY_N, PIPELINE_FACE_EVERY_N
YOLO_IMGSZ, MJPEG_JPEG_QUALITY

# Alerts
ALERT_COOLDOWN_SECONDS
ALERT_EMAIL_ENABLED, ALERT_EMAIL_SMTP_HOST, ALERT_EMAIL_SMTP_PORT,
ALERT_EMAIL_SENDER, ALERT_EMAIL_PASSWORD, ALERT_EMAIL_RECIPIENT
ALERT_WEBHOOK_ENABLED, ALERT_WEBHOOK_URL
ALERT_TELEGRAM_ENABLED, ALERT_TELEGRAM_BOT_TOKEN, ALERT_TELEGRAM_CHAT_ID

# Anomaly Thresholds
LOITERING_SECONDS, CROWD_THRESHOLD
VIOLENCE_VELOCITY_THRESHOLD, VIOLENCE_PROXIMITY_THRESHOLD

# Stream
STREAM_FPS_TARGET, STREAM_RECONNECT_ERROR_THRESHOLD

# Modules
MODULE_WEAPON_ENABLED, MODULE_WEAPON_MODEL, MODULE_WEAPON_CONFIDENCE
MODULE_PPE_ENABLED, MODULE_PPE_MODEL, MODULE_PPE_CONFIDENCE, MODULE_PPE_REQUIRED_ITEMS
MODULE_ANOMALY_ENABLED

# Startup
STARTUP_CAMERAS
```

---

## 14. System Flow Diagrams

### 14.1 Camera Startup Flow

```
Server Start (uvicorn)
    │
    ▼
api/main.py: lifespan()
    │
    ├── init_db() ─────────────────────── Create tables
    ├── get_identities() ──────────────── Load from DB
    ├── camera_service.load_identities() ── Populate ReID + Face engines
    ├── camera_service.restore_cameras() ── Read data/cameras.json
    │       │
    │       ▼
    │   _CameraService.add_camera(cam_id, url, label)
    │       │
    │       ├── _get_reid_engine()      ── Lazy init OSNet + FAISS
    │       ├── _get_face_recognizer()  ── Lazy init InsightFace
    │       ├── _get_zone_manager()     ── Lazy init + watchdog
    │       ├── _get_alert_manager()    ── Lazy init + wire WS/DB/snapshot
    │       ├── _get_module_registry()  ── Lazy init + register modules
    │       │
    │       ▼
    │   MultiCamManager.add_camera()
    │       │
    │       ├── Create CameraPipeline(shared singletons)
    │       ├── Spawn daemon thread → pipeline.start_sync()
    │       └── Persist to cameras.json
    │
    ├── camera_service.start_listener() ── Alert queue listener thread
    └── _load_startup_cameras()         ── Parse STARTUP_CAMERAS env
```

### 14.2 Per-Frame Processing Flow

```
VideoSource Thread                Pipeline Thread
    │                                  │
    ├── cap.read() ──► frame ────────► get_latest_frame()
    │   (deque[2])                     │
    │                                  ├── Skip if same frame ID
    │                                  ├── Skip if not AI frame (every Nth)
    │                                  │
    │                                  ▼
    │                          _process_frame_ai(frame)
    │                                  │
    │                                  ├── 1. Detector.detect(frame)
    │                                  │      → [Detection(person), Detection(weapon)]
    │                                  │
    │                                  ├── 2. Tracker.update(person_dets, frame)
    │                                  │      → [Track(id=1, bbox), Track(id=2, bbox)]
    │                                  │
    │                                  ├── 3. _smooth_bboxes(tracks) — EMA
    │                                  │
    │                                  ├── 4. _process_identities()
    │                                  │      ├── ReID.extract_embedding(crop)
    │                                  │      ├── ReID.get_or_create_global_id()
    │                                  │      ├── FaceRecognizer.analyze(crop)
    │                                  │      └── merge_identities() if face match
    │                                  │
    │                                  ├── 5. _handle_lost_tracks() → move_to_lost()
    │                                  │
    │                                  ├── 6. _periodic_maintenance()
    │                                  │      └── merge_duplicates() every 50 frames
    │                                  │
    │                                  ├── 7. _check_weapons() → WeaponDetector
    │                                  │
    │                                  ├── 8. _process_zones()
    │                                  │      └── ZoneManager.check_intrusions()
    │                                  │
    │                                  └── 9. _process_modules()
    │                                         └── For each enabled module: process()
    │                                  │
    │                                  ▼
    │                          _annotate_and_push()
    │                                  │
    │                                  ├── _draw_annotations() — zones, boxes, labels
    │                                  └── MJPEGBuffer.push_frame(annotated)
    │                                         │
    │                                         ▼
    │                              call_soon_threadsafe()
    │                                         │
    │                                         ▼
    │                              asyncio Queue → frame_generator()
    │                                         │
    │                                         ▼
    │                              StreamingResponse → Browser <img>
```

### 14.3 Alert Dispatch Flow

```
Pipeline Thread                    Alert System
    │                                  │
    ├── zone intrusion detected ──────►│
    │   or weapon detected             │
    │   or anomaly detected            │
    │                                  ▼
    │                          alert_queue.put((event, frame, cam_id))
    │                                  │
    │                                  ▼
    │                          AlertQueueListener thread
    │                                  │
    │                                  ▼
    │                          AlertManager.dispatch(event, frame, cam_id)
    │                                  │
    │                                  ├── _build_alert_from_event() — duck-typing
    │                                  │
    │                                  ├── Cooldown check:
    │                                  │   weapon → bypass
    │                                  │   face_match → 300s per global_id
    │                                  │   others → 60s per (cam, zone, track, type)
    │                                  │
    │                                  ├── ThreadPoolExecutor.submit()
    │                                  │
    │                                  ▼
    │                          _dispatch_async_handlers() [worker thread]
    │                                  │
    │                                  ├── 1. save_snapshot(frame) → disk
    │                                  ├── 2. insert_event(alert) → DB
    │                                  ├── 3. broadcast_event(payload) → WebSocket
    │                                  ├── 4. send_alert_email() → SMTP
    │                                  ├── 5. post_webhook() → HTTP POST
    │                                  └── 6. send_telegram_alert() → Bot API
    │                                         │
    │                                         ▼
    │                                  Dashboard receives WS message
    │                                  → Toast notification
    │                                  → Event list update
    │                                  → Weapon alarm overlay (if weapon)
```

### 14.4 Identity Lifecycle

```
Person enters camera view
    │
    ▼
Tracker assigns local track_id (per-camera)
    │
    ▼
ReID extracts embedding from person crop
    │
    ▼
ReID.get_or_create_global_id()
    ├── Match in local_to_global? → return cached gid
    ├── Match in lost_pool? → reclaim identity
    ├── Match in FAISS gallery? → link to existing gid
    └── No match → create new UUID
    │
    ▼
Track stability check (10 frames same gid)
    │
    ▼
_register_new_person() [daemon thread]
    ├── Save reference snapshot
    ├── Persist to DB (upsert_identity)
    ├── Mark as db_saved in ReID engine
    └── Dispatch IDENTITY_REGISTERED alert
    │
    ▼
Face recognition (every 5th AI frame)
    ├── Match known face? → merge_identities(face_gid, reid_gid)
    ├── Unknown face? → no action (user can enroll via UI)
    └── No face detected? → continue with ReID-only identity
    │
    ▼
Person leaves camera view
    ├── _handle_lost_tracks() → move_to_lost(gid)
    │   (90s in lost_pool for quick re-match)
    └── Gallery TTL: 15min for transients, permanent for DB-persisted

User actions (via Dashboard):
    ├── Rename identity → update_identity_name() + propagate to FaceRecognizer
    ├── Enroll face → face.enroll() + persist embedding
    └── Delete identity → delete_identity() + remove snapshot file
```

---

## 15. Feature-to-Code Mapping

| Feature | Primary Files | Entry Point |
|---------|--------------|-------------|
| Camera stream capture | `engine/stream/source.py` | `VideoSource._capture_loop()` |
| MJPEG browser streaming | `engine/stream/mjpeg.py`, `api/routers/stream.py` | `MJPEGBuffer.frame_generator()` |
| Person detection | `engine/vision/detector.py` | `Detector.detect()` |
| Person tracking | `engine/vision/tracker.py` | `Tracker.update()` |
| Cross-camera Re-ID | `engine/vision/reid.py` | `ReIDEngine.get_or_create_global_id()` |
| Face recognition | `engine/vision/face.py` | `FaceRecognizer.analyze()` |
| Face enrollment | `engine/vision/face.py`, `api/routers/identities.py` | `FaceRecognizer.enroll()` |
| Zone intrusion detection | `engine/zones/manager.py`, `engine/zones/geometry.py` | `ZoneManager.check_intrusions()` |
| Zone hot-reload | `engine/zones/manager.py` | `ZoneManager._setup_watchdog()` |
| Weapon detection | `engine/vision/weapon.py`, `engine/vision/modules/weapon_module.py` | `WeaponDetector.check()` |
| Threat classification | `engine/vision/weapon.py` | `_classify_threat()` |
| Weapon-person association | `engine/vision/weapon.py` | `WeaponDetector._find_holder()` |
| Loitering detection | `engine/vision/anomaly.py` | `AnomalyDetector._check_loitering()` |
| Crowd detection | `engine/vision/anomaly.py` | `AnomalyDetector._check_crowding()` |
| Violence detection | `engine/vision/anomaly.py` | `AnomalyDetector._check_violence_kinematic()` |
| PPE compliance | `engine/vision/modules/ppe_module.py` | `PPEModule.process()` |
| Alert deduplication | `engine/alerts/manager.py` | `AlertManager._check_and_update_cooldown()` |
| Email alerts | `engine/alerts/email.py` | `send_alert_email()` |
| Webhook alerts | `engine/alerts/webhook.py` | `post_webhook()` |
| Telegram alerts | `engine/alerts/telegram.py` | `send_telegram_alert()` |
| Real-time WebSocket push | `api/routers/ws.py` | `ConnectionManager.broadcast()` |
| JWT authentication | `api/middleware/auth.py`, `api/routers/auth.py` | `get_current_user()` |
| Rate limiting | `api/limiter.py`, `api/routers/auth.py` | `@limiter.limit("5/minute")` |
| BBox smoothing | `engine/pipeline.py` | `CameraPipeline._smooth_bboxes()` |
| Frame skip optimization | `engine/pipeline.py` | `pipeline_process_every_n` |
| Identity registration | `engine/pipeline.py` | `CameraPipeline._register_new_person()` |
| Duplicate identity merge | `engine/vision/reid.py` | `ReIDEngine.merge_duplicates()` |
| Multi-camera management | `engine/manager.py` | `MultiCamManager` |
| Camera persistence | `engine/manager.py` | `MultiCamManager._persist()` |
| Module system | `engine/vision/modules/registry.py` | `ModuleRegistry` |
| Frame annotation | `engine/pipeline.py` | `_draw_annotations()` |
| Snapshot saving | `engine/storage/snapshots.py` | `save_snapshot()` |
| DB abstraction | `engine/storage/db.py` | `_get_backend()` |
| Frontend state | `dashboard/src/store/useStore.js` | Zustand `create()` |
| Live camera grid | `dashboard/src/pages/LiveView.jsx` | MJPEG `<img>` tags |
| Dashboard routing | `dashboard/src/App.jsx` | React Router |

---

## 16. Complete Feature List

### Detection & Tracking
- [x] Real-time person detection (YOLOv11l, CUDA FP16)
- [x] Stable per-camera tracking (BoT-SORT)
- [x] Cross-camera person re-identification (OSNet-AIN + FAISS)
- [x] Multi-shot gallery with viewpoint diversity (12 shots/person)
- [x] Face detection and recognition (InsightFace ArcFace)
- [x] Face enrollment from uploaded images
- [x] Face-ReID identity fusion and merging
- [x] Automatic duplicate identity merging
- [x] Bounding box EMA smoothing
- [x] Adaptive CLAHE preprocessing for low-light
- [x] Frame skip optimization (configurable AI frequency)

### Threat Detection
- [x] Weapon detection (dedicated model + COCO fallback)
- [x] Threat level classification (CRITICAL/HIGH/MEDIUM)
- [x] Weapon-person association (overlap + proximity)
- [x] Temporal confirmation (2/5 frames)
- [x] Loitering detection (configurable duration threshold)
- [x] Crowd detection (configurable person count threshold)
- [x] Violence detection (kinematic analysis: velocity + proximity + IoU)
- [x] PPE compliance checking (helmet, vest, gloves, goggles, boots)

### Zone System
- [x] Virtual zone polygon definition (per-camera)
- [x] Real-time intrusion detection (ray-casting algorithm)
- [x] Bottom-center test point (feet-on-ground accuracy)
- [x] Hot-reload via file watcher (watchdog)
- [x] Atomic file writes (crash-safe)
- [x] Zone CRUD API (create, read, update, delete)
- [x] Interactive zone editor in dashboard

### Alert System
- [x] Per-type cooldown deduplication (60s standard, 300s face, none for weapons)
- [x] JPEG snapshot capture on alert
- [x] Database event logging
- [x] Real-time WebSocket push to dashboard
- [x] Email alerts (async SMTP with snapshot attachment)
- [x] Webhook alerts (HTTP POST with JSON payload)
- [x] Telegram alerts (MarkdownV2 with photo)
- [x] Alert channel test endpoint
- [x] In-app toast notifications with severity levels
- [x] Full-screen weapon alarm overlay

### API & Security
- [x] JWT Bearer authentication (HS256, configurable expiry)
- [x] Query-param token auth for streams and snapshots
- [x] WebSocket token validation before accept
- [x] Rate limiting on login (5/min per IP)
- [x] CORS configuration (origin, method, header restrictions)
- [x] Path traversal prevention on snapshot serving
- [x] Camera URL scheme validation (SSRF prevention)
- [x] Request logging without query params (token leak prevention)
- [x] Sensitive field masking in API responses

### Streaming
- [x] MJPEG over HTTP (browser-native)
- [x] HTTP, RTSP, and local camera support
- [x] Auto-reconnect with exponential backoff (2s–32s)
- [x] Low-latency RTSP (TCP transport, buffer draining)
- [x] Frame deduplication (skip already-processed frames)
- [x] Non-blocking frame push (drop-oldest queue)

### Storage
- [x] SQLite backend (zero-setup, WAL mode)
- [x] PostgreSQL backend (connection pooling, production-grade)
- [x] Swappable via `DB_URL` environment variable
- [x] Unified facade API (callers don't know which backend)
- [x] Identity persistence with embedding storage
- [x] Camera registry persistence (JSON)
- [x] Module state persistence (JSON)

### Dashboard
- [x] Login page with JWT auth
- [x] Live camera grid (2x2/3x3 layout)
- [x] Real-time event feed via WebSocket
- [x] Paginated event log with filters
- [x] Identity management (view, rename, enroll face, delete)
- [x] Zone editor with interactive polygon drawing
- [x] Alert configuration (email, webhook, Telegram)
- [x] Analytics dashboard with statistics
- [x] Module management (enable/disable/configure)
- [x] Dark/light theme toggle
- [x] WebSocket auto-reconnect with backoff
- [x] Toast notification stack

### DevOps
- [x] Docker Compose (PostgreSQL + engine + dashboard)
- [x] NVIDIA GPU passthrough (runtime: nvidia)
- [x] Environment-based configuration (.env)
- [x] Startup camera auto-loading (STARTUP_CAMERAS)
- [x] Graceful shutdown (pipeline stop, executor drain, watchdog cleanup)
- [x] Health check endpoint (/health — unauthenticated)

---

## 17. Data Model & Schema

### 17.1 Persistence Files

| File | Format | Purpose | Written By |
|------|--------|---------|------------|
| `data/cameras.json` | JSON array | Camera registry | `MultiCamManager._persist()` |
| `data/zones.json` | JSON array | Zone polygons | `ZoneManager._save_atomic()` |
| `data/modules.json` | JSON object | Module enabled/config state | `ModuleRegistry._persist()` |
| `data/sentinal.db` | SQLite | Events, identities, cameras, zones | `SQLiteBackend` |
| `data/snapshots/` | JPEG files | Alert snapshots | `save_snapshot()` |
| `data/snapshots/identities/` | JPEG files | Identity reference photos | `_register_new_person()`, `face.enroll()` |

### 17.2 Runtime Data Structures

| Structure | Location | Thread Safety | Purpose |
|-----------|----------|---------------|---------|
| FAISS IndexFlatIP(512) | `ReIDEngine.gallery` | RLock | Fast cosine similarity search |
| `shot_store` | `ReIDEngine` | RLock | Multi-shot embedding gallery per person |
| `local_to_global` | `ReIDEngine` | RLock | Camera-local track → global UUID mapping |
| `lost_pool` | `ReIDEngine` | RLock | Recently-lost identities for re-match |
| `known_embeddings` | `FaceRecognizer` | RLock | Name → embedding map for face matching |
| `_cooldowns` | `AlertManager` | RLock | Dedup key → expiry timestamp |
| `zones` | `ZoneManager` | RLock | Active zone polygon list |
| `_cameras` | `MultiCamManager` | RLock | Active pipeline registry |
| `active_connections` | `ConnectionManager` | asyncio.Lock | WebSocket client list |

---

## 18. Deployment

### 18.1 Development

```bash
# Backend
source .venv/Scripts/activate
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd dashboard/
npm install
npm run dev  # port 5173
```

### 18.2 Production (Docker Compose)

```yaml
services:
  postgres:   # PostgreSQL 16 Alpine
  engine:     # FastAPI + AI models (NVIDIA runtime)
  dashboard:  # React build served via Nginx
```

All services use `network_mode: host` for simplicity on a single-machine deployment.

### 18.3 Required Model Files

| Model | Path | Size | Purpose |
|-------|------|------|---------|
| YOLOv11l | `models/yolo11l.pt` | ~50MB | Person + weapon detection |
| OSNet-AIN x1.0 | `models/osnet_ain_x1_0_msmt17_*.pth` | ~18MB | Person re-identification |
| InsightFace buffalo_l | Auto-downloaded by insightface | ~300MB | Face recognition |
| YOLOv8s weapons (optional) | `models/yolov8s_weapons.pt` | ~22MB | Dedicated weapon model |
| YOLOv8s PPE (optional) | `models/yolov8s_ppe.pt` | ~22MB | PPE compliance model |

---

## 19. File Index

### Engine (`engine/`) — 5,800 lines

| File | Lines | Purpose |
|------|-------|---------|
| `config.py` | 121 | Pydantic settings, .env loader |
| `pipeline.py` | 827 | Per-camera AI pipeline (main loop) |
| `manager.py` | 190 | Multi-camera orchestrator |
| `launcher.py` | 29 | Process launcher (unused) |
| `vision/detector.py` | 191 | YOLO person+weapon detection |
| `vision/tracker.py` | 125 | BoT-SORT tracking wrapper |
| `vision/reid.py` | 611 | OSNet-AIN Re-ID + FAISS |
| `vision/face.py` | 315 | InsightFace ArcFace recognition |
| `vision/weapon.py` | 256 | Weapon filter + threat classification |
| `vision/anomaly.py` | 251 | Rule-based anomaly detection |
| `vision/modules/base.py` | 104 | Detection module ABC |
| `vision/modules/registry.py` | 179 | Module lifecycle manager |
| `vision/modules/weapon_module.py` | 211 | Weapon detection module |
| `vision/modules/ppe_module.py` | 218 | PPE compliance module |
| `vision/modules/anomaly_module.py` | 62 | Anomaly detection module |
| `zones/geometry.py` | 134 | Ray-casting + IoU |
| `zones/manager.py` | 242 | Zone CRUD + intrusion detection |
| `alerts/manager.py` | 358 | Alert dispatch + deduplication |
| `alerts/email.py` | 117 | SMTP email sender |
| `alerts/webhook.py` | 102 | HTTP webhook sender |
| `alerts/telegram.py` | 148 | Telegram Bot API sender |
| `storage/base.py` | 100 | DB backend ABC |
| `storage/sqlite.py` | 335 | SQLite implementation |
| `storage/postgres.py` | 345 | PostgreSQL implementation |
| `storage/db.py` | 118 | Unified facade |
| `storage/snapshots.py` | 45 | JPEG snapshot writer |
| `stream/source.py` | 180 | Threaded camera reader |
| `stream/mjpeg.py` | 88 | MJPEG async buffer |

### API (`api/`) — 1,500 lines

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 190 | FastAPI app, lifespan, middleware |
| `limiter.py` | 6 | Shared rate limiter |
| `middleware/auth.py` | 67 | JWT validation dependencies |
| `services/camera_service.py` | 273 | Singleton service layer |
| `services/auth_service.py` | 16 | bcrypt wrappers |
| `routers/auth.py` | 48 | Login endpoint |
| `routers/cameras.py` | 124 | Camera CRUD |
| `routers/stream.py` | 40 | MJPEG stream |
| `routers/ws.py` | 100 | WebSocket broadcaster |
| `routers/events.py` | 106 | Event log + snapshots |
| `routers/zones.py` | 146 | Zone CRUD |
| `routers/identities.py` | 125 | Identity management |
| `routers/alerts.py` | 246 | Alert configuration |
| `routers/stats.py` | 85 | Analytics endpoint |
| `routers/modules.py` | 81 | Module management |

### Dashboard (`dashboard/src/`) — 4,800 lines

| File | Lines | Purpose |
|------|-------|---------|
| `store/useStore.js` | 401 | Zustand global state |
| `pages/LiveView.jsx` | 422 | Camera grid |
| `pages/Events.jsx` | 442 | Event log |
| `pages/Alerts.jsx` | 431 | Alert settings |
| `pages/Cameras.jsx` | 332 | Camera management |
| `pages/Identities.jsx` | 317 | Identity CRUD |
| `pages/Zones.jsx` | 298 | Zone editor |
| `pages/Analytics.jsx` | 262 | Statistics |
| `pages/Login.jsx` | 233 | Authentication |
| `pages/Modules.jsx` | 205 | Module control |
| `components/ZoneEditor.jsx` | 283 | Polygon drawing |
| `components/AlertBanner.jsx` | 209 | Weapon alarm overlay |
| `components/ToastStack.jsx` | 133 | Notification toasts |
| `components/ZoneOverlay.jsx` | 79 | Zone polygon SVG |
| `components/PersonBadge.jsx` | 39 | Identity chip |

---

*End of document.*
