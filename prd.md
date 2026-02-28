# SENTINALv1 — Product Requirements Document (PRD)

**Version**: 1.0 MVP  
**Date**: 2026-02-28  
**Status**: Active Development

---

## 1. Product Vision

SENTINALv1 is a **local-first, open-source AI surveillance system** that provides real-time person detection, persistent tracking, zone-based intrusion detection, and alert logging — entirely on-premises, without any paid API or cloud dependency.

---

## 2. Target Users

| Persona                    | Use Case                                                                       |
| -------------------------- | ------------------------------------------------------------------------------ |
| **Home Security Hobbyist** | Monitor entry points with a webcam, get alerts when specific zones are crossed |
| **Small Business Owner**   | Track foot traffic in restricted areas, log intrusions to a database           |
| **Security Researcher**    | Prototype and test computer vision surveillance pipelines                      |
| **System Integrator**      | Embed as a headless engine into a larger multi-camera security system          |

---

## 3. Goals and Non-Goals

### Goals ✅

- Detect and track people in real time using a CPU-optimised model (YOLOv8n)
- Assign persistent IDs that survive brief exits and re-entries (Re-ID)
- Trigger intrusion alerts when a track crosses a user-defined polygon zone
- Log alerts to CSV and optionally to PostgreSQL with visual snapshots
- Provide both a desktop GUI (PyQt5) and a web dashboard (React)
- Run fully offline with no paid dependencies

### Non-Goals ❌

- Face recognition or biometric identification
- Audio surveillance
- Multi-camera synchronisation (v1 scope)
- Mobile app
- Cloud streaming / SaaS hosting

---

## 4. Functional Requirements

### FR-1: Video Ingestion

- **FR-1.1** System shall support webcam (index-based) and local video file sources
- **FR-1.2** System shall buffer at most 2 frames to prevent stale-frame display
- **FR-1.3** Frame resolution shall be configurable via environment variable (default 640×360)

### FR-2: Person Detection & Tracking

- **FR-2.1** System shall detect persons using YOLOv8n with confidence threshold ≥ 0.4
- **FR-2.2** System shall assign short-term track IDs using ByteTrack
- **FR-2.3** System shall draw bounding boxes and track IDs on the display frame

### FR-3: Re-Identification

- **FR-3.1** System shall assign `stable_id` that persists across track drops using feature similarity
- **FR-3.2** Re-ID shall use cosine similarity of deep feature embeddings (≥ 0.60 threshold)
- **FR-3.3** Re-ID memory (TTL) shall default to 15 seconds, configurable via env var
- **FR-3.4** Re-ID inference shall be batched per frame to minimise latency

### FR-4: Zone Intrusion Detection

- **FR-4.1** System shall support user-defined convex polygon zones
- **FR-4.2** System shall fire a `ZoneEvent` on first entry of a track into a zone per session
- **FR-4.3** Zone polygons shall be configurable without code changes (target: API/UI in v2)

### FR-5: Alert Logging

- **FR-5.1** System shall log each intrusion event to a persistent CSV file
- **FR-5.2** System shall save a JPEG snapshot frame for each alert
- **FR-5.3** System shall optionally persist events to PostgreSQL when `DATABASE_URL` is set
- **FR-5.4** System shall suppress duplicate alerts within a configurable cooldown (default 10s)
- **FR-5.5** Snapshot saves and DB inserts shall be non-blocking (daemon threads)

### FR-6: Desktop GUI

- **FR-6.1** GUI shall display the live annotated video feed using PyQt5
- **FR-6.2** GUI shall allow switching between webcam and video file sources
- **FR-6.3** GUI shall display real-time FPS (smoothed via EMA)

### FR-7: Web Dashboard

- **FR-7.1** Dashboard shall display an MJPEG live feed from the backend
- **FR-7.2** Dashboard shall show a real-time event log with zone, track ID, camera ID, timestamp
- **FR-7.3** Dashboard shall allow viewing snapshot images linked to events

### FR-8: API Backend

- **FR-8.1** Backend shall expose `GET /events` returning the last N intrusion events
- **FR-8.2** Backend shall expose `GET /stream/{camera_id}` for MJPEG streaming
- **FR-8.3** Backend shall expose `GET /zones` returning active zone configurations
- **FR-8.4** Backend shall expose `GET /health` for liveness checks

---

## 5. Non-Functional Requirements

| NFR                   | Requirement                                                         |
| --------------------- | ------------------------------------------------------------------- |
| **Performance**       | ≥ 10 FPS on a mid-range CPU (Intel i5 / Ryzen 5) without GPU        |
| **Latency**           | Display lag ≤ 200ms from camera to screen                           |
| **Reliability**       | System shall not crash on camera disconnect; it shall log and retry |
| **Security**          | `.env` must not be committed; no secrets hardcoded in source        |
| **Extensibility**     | New zones must be addable without modifying Python source code      |
| **Portability**       | Shall run on Windows 10+ and Ubuntu 22.04+                          |
| **Container Support** | Backend + DB shall be deployable via `docker-compose up`            |

---

## 6. System Constraints

- CPU-only inference (no CUDA required)
- Single camera (MVP)
- No face recognition (privacy constraint)
- No internet connectivity required

---

## 7. Milestones

| Milestone                                           | Status                   |
| --------------------------------------------------- | ------------------------ |
| M1: Core detection + tracking (YOLOv8n + ByteTrack) | ✅ Complete              |
| M2: Zone intrusion + CSV alert logging              | ✅ Complete              |
| M3: PyQt5 Desktop GUI                               | ✅ Complete              |
| M4: FastAPI backend + MJPEG stream                  | ✅ Complete              |
| M5: React/Vite Web Dashboard                        | ✅ Complete              |
| M6: MobileNetV3 Re-ID stitcher                      | ✅ Complete              |
| M7: Docker containerisation                         | ✅ Complete (backend+DB) |
| M8: Runtime zone editor (UI)                        | ❌ Not started           |
| M9: WebSocket real-time events                      | ❌ Not started           |
| M10: Multi-camera support                           | ❌ Not started           |
| M11: Dedicated Re-ID model (OSNet)                  | ❌ Not started           |
