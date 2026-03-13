# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# SENTINAL v2 — AI Surveillance System

## Project Overview
SENTINAL is a zero-cloud, on-premise AI video surveillance system. It detects and tracks people across multiple camera feeds, identifies intruders, recognizes faces, detects weapons, and logs all events with snapshots to a local database. The system has a FastAPI backend (AI engine) and a React dashboard frontend.

## Hardware Setup
- **AI Server**: RTX 4050 laptop (CUDA) — runs all AI models + FastAPI backend
- **Client**: Zenbook 14 (Arc 130T) — browser-only, accesses dashboard via local network
- **Cameras**: Android phones running DroidCam or IP Webcam app over WiFi

## Repository Structure
```
SENTINALv2/
├── CLAUDE.md              ← you are here
├── engine/                ← AI Core (pure Python, no UI)
│   ├── config.py          ← Pydantic settings, loads from .env
│   ├── pipeline.py        ← Per-camera pipeline (generator pattern)
│   ├── manager.py         ← MultiCamManager (orchestrates all cameras)
│   ├── vision/
│   │   ├── detector.py    ← YOLOv8n — person + weapon detection (CUDA)
│   │   ├── tracker.py     ← BoT-SORT wrapper (stable track IDs)
│   │   ├── reid.py        ← OSNet-x0.25 cross-camera Re-ID + FAISS
│   │   ├── face.py        ← InsightFace ArcFace recognition + naming
│   │   ├── anomaly.py     ← Rule-based: loitering, crowding, violence
│   │   └── weapon.py      ← YOLO weapon class filter + alarm trigger
│   ├── zones/
│   │   ├── manager.py     ← ZoneManager (hot-reload from zones.json)
│   │   └── geometry.py    ← Ray-casting polygon engine (bottom-center test)
│   ├── alerts/
│   │   ├── manager.py     ← Dedup, cooldown (60s default), dispatch
│   │   ├── email.py       ← SMTP alert sender
│   │   └── webhook.py     ← HTTP POST webhook
│   ├── storage/
│   │   ├── db.py          ← PostgreSQL pool (psycopg2); SQLite fallback
│   │   └── snapshots.py   ← JPEG snapshot writer (data/snapshots/)
│   └── stream/
│       ├── source.py      ← VideoSource: threaded, auto-reconnect, CAP_PROP_BUFFERSIZE=1
│       └── mjpeg.py       ← MJPEG frame buffer (deque, push model)
├── api/                   ← FastAPI backend
│   ├── main.py            ← App entry, lifespan, CORS
│   ├── routers/
│   │   ├── cameras.py     ← POST/DELETE /cameras
│   │   ├── stream.py      ← GET /stream/{cam_id} (MJPEG)
│   │   ├── events.py      ← GET /events
│   │   ├── zones.py       ← GET/POST /zones
│   │   ├── identities.py  ← GET/PUT /identities
│   │   ├── stats.py       ← GET /stats
│   │   ├── alerts.py      ← GET/PUT /alerts config
│   │   └── ws.py          ← WS /ws/live (real-time event push)
│   └── services/
│       ├── camera_service.py ← Singleton MultiCamManager wrapper
│       └── db_service.py     ← DB query helpers
├── dashboard/             ← React 18 + Vite frontend
│   └── src/
│       ├── pages/         ← LiveView, Events, Identities, Zones, Alerts, Analytics
│       ├── components/    ← CameraCard, EventFeed, ZoneEditor, PersonBadge, AlertBanner
│       └── store/         ← Zustand global state
├── models/                ← Local model weights (not committed to git)
│   ├── yolov8n.pt
│   ├── yolov8_weapon.pt
│   └── osnet_x0_25.pth
├── data/
│   ├── zones.json         ← Active zone polygon definitions
│   ├── snapshots/         ← Alert snapshots (auto-created)
│   └── logs/              ← CSV fallback logs
├── .env                   ← All config (never commit)
├── docker-compose.yml
└── requirements.txt
```

## Tech Stack
- **Detection**: YOLOv11l (large) via Ultralytics (CUDA, FP16)
- **Tracking**: BoT-SORT (built into Ultralytics)
- **Re-ID**: OSNet-x0.25 via torchreid (trained on Market-1501/DukeMTMC)
- **Face Recognition**: InsightFace ArcFace (better than FaceNet)
- **API**: FastAPI with async + WebSocket
- **DB**: PostgreSQL (primary) with SQLite fallback
- **Frontend**: React 18 + Vite + shadcn/ui + Tailwind CSS + Recharts + Zustand
- **Video delivery**: MJPEG over HTTP to browser

## Build Phases (Current Status)
- **Phase 1** ✅ TARGET: One camera, stream working, YOLO detection, tracked in browser
- **Phase 2**: Multi-cam + zones + intrusion events + DB logging + snapshots
- **Phase 3**: Re-ID + Face recognition (OSNet + InsightFace)
- **Phase 4**: Anomaly detection + weapon detection + email/webhook alerts
- **Phase 5**: Full React dashboard (all pages) + Docker + production polish

## Key Commands
```bash
# Backend (activate venv first — .venv/ is in project root)
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd dashboard/
npm install
npm run dev   # runs on port 5173

# Test single camera stream
python -m engine.pipeline --source "http://192.168.x.x:4747/video"
```

## Code Style Rules
- Python: use type hints everywhere, docstrings on all public methods
- Async: use asyncio + ThreadPoolExecutor for blocking I/O (never block the event loop)
- All frame-level operations must be non-blocking (daemon threads for alerts, DB writes)
- Use Pydantic models for all API request/response schemas
- React: functional components + hooks only, no class components
- Import order: stdlib → third-party → local (use isort)
- NEVER hardcode camera URLs, model paths, or credentials — use .env via config.py

## Critical Implementation Notes
- `CAP_PROP_BUFFERSIZE = 1` is MANDATORY on all VideoCapture objects (prevents frame lag)
- Stream reconnect uses exponential backoff: 2s → 4s → 8s → 16s → 32s (max 5 retries)
- Zone intersection uses bottom-center of bounding box, NOT centroid (more accurate for standing persons)
- Re-ID embeddings use EMA update: α=0.90 (smooth identity drift over time)
- Alert dedup: same (camera, zone, track_id) combo ignores re-trigger for 60 seconds
- CLAHE preprocessing MUST be applied before any Re-ID embedding extraction

## Agent Workflow
This project uses a multi-agent build system via `/plan-phase` and `/build-next` skills:
- **orchestrator**: reads CLAUDE.md + SPEC.md, breaks phases into tasks, writes to `postbox/todo.md`
- **gemini-coder**: picks up OPEN tasks from `postbox/todo.md` and implements them
- **haiku-writer**: writes tests, docs, and boilerplate
- **react-builder**: builds React components and pages
- **python-reviewer**: reviews all generated Python code before marking tasks COMPLETED

Task states in `postbox/todo.md`: `OPEN → IN PROGRESS → COMPLETED`

**SPEC.md** is the authoritative source for *what* to build. CLAUDE.md is *how* to build it. Always read both at the start of a new phase.

## What Claude Gets Wrong (DO NOT DO)
- Do NOT use `time.sleep()` in the main pipeline loop — use threading events
- Do NOT use `cv2.imshow()` anywhere — all display is through MJPEG to browser
- Do NOT write to SQLite from multiple threads without a lock — use a write queue
- Do NOT use MobileNetV3 or generic ImageNet models for Re-ID — ONLY OSNet
- Do NOT use FaceNet — ONLY InsightFace ArcFace
- Do NOT install PostgreSQL as a hard requirement in Phase 1 — SQLite first
