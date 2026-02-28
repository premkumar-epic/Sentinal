# SENTINALv1 — Improvement Roadmap

> Ranked by impact vs. implementation effort. Priorities: P0 (Critical) → P3 (Future).

---

## P0 — Fix Immediately (Blocking Production Use)

### IMP-01: Unify the Pipeline Instance

**Fixes**: ISSUE-01  
**What**: Remove the standalone pipeline from `video_service.py`. Instead, `gui.py` or a headless `engine.py` should own the single pipeline, and `video_service.py` should subscribe to its frame buffer (e.g., via a shared `threading.Event` + deque).  
**How**:

```python
# Shared frame buffer (in core/)
_latest_frame: Optional[bytes] = None
_frame_lock = threading.Lock()

# VideoStreamManager reads from this shared buffer
# SurveillancePipeline writes to it
```

### IMP-02: Fix `requirements.txt`

**Fixes**: ISSUE-02  
**What**: Pin all dependencies with exact versions actually installed in `.venv`.

```
ultralytics==8.x.x
opencv-python==4.10.0.84
numpy==1.26.4
torch==2.3.1+cpu
torchvision==0.18.1+cpu
PyQt5==5.15.x
fastapi==0.133.0
uvicorn==0.41.0
pydantic==2.12.5
pydantic-settings==2.13.1
python-dotenv==1.2.1
psycopg2-binary==2.9.11
```

### IMP-03: Add DB Connection Pool

**Fixes**: ISSUE-03  
**What**: Replace raw `psycopg2.connect()` with a thread-safe connection pool.  
**How**: Use `psycopg2.pool.ThreadedConnectionPool` with `minconn=1, maxconn=5`.

---

## P1 — Important (Major UX and Architecture Improvements)

### IMP-04: Fix `gui.py` Config Inheritance on Restart

**Fixes**: ISSUE-04  
**What**: In `_start_pipeline()`, instead of creating a bare `VideoConfig`, copy the full config from `load_config()` and only override `source_type` and `video_path`:

```python
def _start_pipeline(self) -> None:
    cfg = load_config()  # Inherit frame_skip, resolution from .env
    cfg.video.source_type = self._source_combo.currentText()
    cfg.video.video_path = self._video_path if cfg.video.source_type == "video" else None
    ...
```

### IMP-05: Move Zones to a JSON Config File

**Fixes**: ISSUE-05  
**What**: Load zones from `zones.json` instead of hardcoding in `config.py`. Expose a `PUT /zones` API endpoint to update and persist zones at runtime.  
**How**:

```json
// zones.json
[
  {
    "id": "zone_1",
    "label": "Entrance",
    "polygon": [
      [100, 80],
      [540, 80],
      [540, 300],
      [100, 300]
    ]
  }
]
```

### IMP-06: Replace MobileNetV3 with Dedicated Re-ID Model

**Fixes**: ISSUE-06  
**What**: Use a lightweight person Re-ID model trained on pedestrian datasets. Good options:

- **OSNet-x0.25** (Omni-Scale Network) — 2MB, fast CPU, specifically trained for person Re-ID
- **BoT-TransReID** (lightweight) — transformer-based but heavier
- **torchreid** library provides pretrained OSNet weights  
  **Impact**: Dramatically improves Re-ID accuracy in multi-person scenes.

### IMP-07: Eliminate Double Feature Extraction

**Fixes**: ISSUE-07  
**What**: Store the features computed during matching so they can be reused in `_upsert_lost()` without a second inference pass.

### IMP-08: Fix Snapshot Preview in Web UI

**Fixes**: ISSUE-08  
**What**: Serve snapshots as static files from the backend via `StaticFiles`. Add a clickable link or modal in `EventLog.jsx`.

```python
# backend/main.py
from fastapi.staticfiles import StaticFiles
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
```

```jsx
// EventLog.jsx
<a
  href={`http://localhost:8000/snapshots/${evt.snapshot_filename}`}
  target="_blank"
>
  View Snapshot
</a>
```

### IMP-09: Replace REST Polling with WebSocket in Frontend

**Fixes**: ISSUE-10 (partial)  
**What**: Replace the 2-second polling loop in `EventLog.jsx` with a WebSocket connection to a backend `ws://localhost:8000/ws/events` endpoint. Push events immediately when alerts fire.  
**Impact**: Real-time event display, lower server load (no repeated HTTP requests).

### IMP-10: YOLO Model Warm-Up

**Fixes**: ISSUE-11  
**What**: After loading the YOLO model in `ObjectTracker.__init__()`, run a dummy inference pass:

```python
dummy = np.zeros((360, 640, 3), dtype=np.uint8)
self._model.track(source=dummy, conf=self._conf, verbose=False, device="cpu")
```

---

## P2 — High Value Features (Next Sprint)

### IMP-11: Runtime Zone Editor in Web UI

- Drag-to-draw polygon zones on the live feed canvas
- POST to `/zones` to persist immediately without system restart
- Show existing zones as overlays on the stream

### IMP-12: Multi-Camera Support

- Abstract `SurveillancePipeline` to accept a camera ID
- Run multiple pipelines as threads/processes
- `video_service.py` manages a dict of `camera_id → pipeline`
- Frontend shows camera selector

### IMP-13: Dashboard Statistics Panel

- Total intrusions today/7d/30d
- Unique person count (by stable_id)
- Heatmap of foot traffic zones
- Chart of intrusions over time (recharts)

### IMP-14: Alert Notification System

- Push desktop notifications via `plyer` or `win10toast`
- Optional email/webhook dispatch (e.g., ntfy.sh, Pushover)
- Alert sound on intrusion

### IMP-15: Re-ID Confidence Display

- Show cosine similarity score on bounding box label
- Allow threshold adjustment via a UI slider without restart

---

## P3 — Future / Research

### IMP-16: GPU Acceleration via CUDA/DirectML

- Allow `MODEL_DEVICE=cuda` configuration
- Benchmarks suggest 5–10x throughput improvement

### IMP-17: Action Recognition

- Classify what the detected person is doing (running, loitering, falling)
- Integrate a lightweight action recognition model on top of the bounding box ROIs

### IMP-18: Edge Deployment

- Optimise model to ONNX or INT8 quantised format
- Target deployment on Raspberry Pi 5 or Jetson Nano

### IMP-19: Privacy Mode

- Blur / pixelate detected persons in the stored snapshots
- Allow GDPR-compliant data retention policies (auto-delete after N days)

### IMP-20: Proper CI/CD Pipeline

- GitHub Actions: lint (`ruff`), type-check (`mypy`), unit tests (`pytest`), Docker build
- Automatic version tagging and GitHub Release on merge to `main`

---

## Summary Table

| ID                        | Priority | Effort | Impact      |
| ------------------------- | -------- | ------ | ----------- |
| IMP-01 (Unified pipeline) | P0       | Medium | 🔴 Critical |
| IMP-02 (requirements.txt) | P0       | Low    | 🔴 Critical |
| IMP-03 (DB pool)          | P0       | Low    | 🟡 High     |
| IMP-04 (gui.py config)    | P1       | Low    | 🟡 High     |
| IMP-05 (JSON zones)       | P1       | Medium | 🟡 High     |
| IMP-06 (OSNet Re-ID)      | P1       | Medium | 🟡 High     |
| IMP-07 (double inference) | P1       | Low    | 🟡 Medium   |
| IMP-08 (snapshots in UI)  | P1       | Low    | 🟡 Medium   |
| IMP-09 (WebSocket events) | P1       | Medium | 🟡 Medium   |
| IMP-10 (model warmup)     | P1       | Low    | 🟢 Low      |
| IMP-11 (zone editor)      | P2       | High   | 🟡 High     |
| IMP-12 (multi-camera)     | P2       | High   | 🟡 High     |
| IMP-13 (statistics)       | P2       | Medium | 🟢 Medium   |
| IMP-14 (notifications)    | P2       | Low    | 🟢 Medium   |
