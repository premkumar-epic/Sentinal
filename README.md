# SENTINALv1: Production AI Surveillance System

SENTINALv1 is a modular, zero-cloud AI video surveillance MVP designed for local, on-premise execution. It provides real-time YOLOv8n object detection, MobileNet Re-ID persistent tracking, mathematical zone-intrusion detection, and alert logging via a PostgreSQL database.

## Architecture

This system is built for production environments and is cleanly decoupled into a central AI Brain and distributed interfaces.

### `Core_AI/` (The Brain)

The engine that runs the intelligence. Contains no GUI or HTTP code.

- **`pipeline.py`**: The `SurveillancePipeline` generator that yields frames, tracked IDs, and zone events.
- **`tracker.py`**: Auto-detects PyTorch CUDA hardware acceleration for high FPS YOLO execution.
- **`id_stitcher.py`**: Persistent Identity tracking utilizing Exponential Moving Average (EMA) feature embeddings to prevent tracking drift across camera occlusions.
- **`zones.py`**: Mathematical `ray_casting` algorithms calculating whether tracking bounding-box centers intersect with dynamically configured polygon regions.

### `V2_Desktop/` (Standalone Deployment)

The lightweight deployment for a single standalone machine and physical webcam (Case 2: e.g., A Reception Desk).

- Powered by `PyQt5`. Directly pulls from `Core_AI` to draw bounding boxes and bounding box traces natively in Windows with zero network latency.

### `V3_Web/` (Enterprise / Networked Deployment)

The distributed NVR (Network Video Recorder) deployment designed for offices and factories (Cases 1 & 3: e.g., parsing Hikvision/Dahua RTSP IP streams).

- **Backend**: `FastAPI` instance streaming `MJPEG` compressed video over the local network via WebSockets.
- **Frontend**: `React` (Vite) NVR Control Dashboard allowing security guards to view multiple streams, review database Event Logs, and hot-reload Polygon Zones remotely.

## Installation

Ensure you have Python 3.10+ and (optionally) Node.js installed.

1. Clone the repository and install the environment.

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

2. Select your deployment strategy.

**For V2 Desktop:**

```bash
pip install -r V2_Desktop/requirements_v2.txt
python V2_Desktop/app.py
```

**For V3 Web:**

```bash
# Terminal 1 (AI Backend System)
pip install -r V3_Web/backend/requirements_v3.txt
python V3_Web/backend/main.py

# Terminal 2 (React Dashboard Interface)
cd V3_Web/frontend
npm install
npm run dev
```

## Production Considerations

- **Hardware Acceleration:** SENTINAL automatically checks for NVidia GPU capabilities via `torch.cuda.is_available()`. Ensure appropriate PyTorch CUDA drivers are installed on the host machine to easily exceed 30+ FPS.
- **PostgreSQL Database:** By default, alerts only log to `logs/sentinal.log` if `DATABASE_URL` is empty. Set your `.env` appropriately to enable persistent PostgreSQL tracking.
- **Zone Hot-Reloading:** In V3 Web, creating a zone on the UI canvas pushes a REST command to the Backend, which automatically injects the new polygon coordinates into the running `SurveillancePipeline` without dropping video frames.
