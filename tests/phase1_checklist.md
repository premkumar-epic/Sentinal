# SENTINAL v2 — Phase 1 Checklist & Manual Test Plan

This document outlines the requirements for **Phase 1: Solid Foundation** as defined in `SPEC.md` and provides a manual test plan to verify the implementation.

---

## 📋 Phase 1 Requirements Checklist

### 1. Backend Foundation
- [x] **Config System**: Pydantic `BaseSettings` loading from `.env`.
- [x] **Database**: SQLite initialized with the 4-table schema (events, identities, cameras, zones).
- [x] **API Entry**: FastAPI app with lifespan handling (DB init, camera restoration).
- [x] **CORS**: Configured to allow frontend access from localhost and local IP.

### 2. Stream Layer
- [x] **VideoSource**: Threaded reader, `CAP_PROP_BUFFERSIZE=1` set, daemon=True.
- [x] **Auto-Reconnect**: Exponential backoff (2s → 4s → 8s → 16s → 32s).
- [x] **Webcam Support**: Handles numeric indices (e.g., "0") and `CAP_DSHOW` on Windows.
- [x] **MJPEGBuffer**: Thread-safe push model using `asyncio.Queue`.

### 3. AI Vision Pipeline
- [x] **Detector**: YOLO11n loaded to CUDA (or CPU fallback).
- [x] **Person Detection**: COCO class 0 filtering.
- [x] **Weapon Detection**: Filtering for weapon keywords (knife, gun, etc.).
- [x] **Tracker**: BoT-SORT (via boxmot) or fallback ID assignment.
- [x] **Annotation**: BGR drawing (green for persons, red for weapons, status bar).

### 4. Camera Management
- [x] **MultiCamManager**: Singleton `camera_service` managing pipelines.
- [x] **Persistence**: `data/cameras.json` updated on camera add/remove/patch.
- [x] **Endpoints**: POST (add), DELETE (remove), GET (list), PATCH (update).

### 5. Frontend (Phase 1 Milestone)
- [x] **LiveView**: CSS Grid (1x1, 2x2, 3x3) layout.
- [x] **Streaming**: `<img>` tags consuming MJPEG multipart streams.
- [x] **Status Indicators**: Green/Red dots for camera and WebSocket status.
- [x] **Weapon Alarm**: Full-screen red overlay (frontend triggerable via WS).

---

## 🧪 Manual Testing Procedure

### Test 1: Camera Setup
1. Open the browser to `http://localhost:5173`.
2. Check if your webcam feed appears in the grid.
3. **Pass Criteria**: Webcam light turns on, feed is visible with a green "cam0" label and status dot.

### Test 2: AI Detection & Tracking
1. Walk into the camera frame.
2. Observe the bounding box.
3. **Pass Criteria**: A **green box** appears around you with an "ID:X" label. The ID should stay consistent while you are in frame.

### Test 3: Weapon Alarm (Mock Test)
1. Show a clear image of a knife or gun to the webcam (or use a prop).
2. **Pass Criteria**: A **red box** appears around the object. The dashboard should trigger a **full-screen red banner** saying "WEAPON DETECTED".

### Test 4: Performance & Latency
1. Wave your hand in front of the camera.
2. Count the delay between your hand moving and the screen updating.
3. **Pass Criteria**: Lag should be **under 500ms**. If lag is 2-3 seconds, `CAP_PROP_BUFFERSIZE=1` might not be taking effect.

### Test 5: Persistence
1. Stop the backend server (Ctrl+C).
2. Start the backend server again.
3. Refresh the dashboard.
4. **Pass Criteria**: The camera feed should automatically restart without having to add it again.

### Test 6: UI Responsiveness
1. Switch between 1x1, 2x2, and 3x3 layouts.
2. Resize the browser window.
3. **Pass Criteria**: The camera feed scales appropriately. Scrolling is enabled if the feed is larger than the viewport.

---

## 🛠 Known Issues & Tuning
- **Lag**: If detection is slow, ensure you are using CUDA (check backend logs). YOLO11n on CPU can add 100-200ms of lag.
- **Webcam Access**: Only one application can use the webcam at a time. Close other apps (Zoom, Teams, Camera app) before starting.
