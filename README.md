# SENTINAL v2 — AI Video Surveillance System

SENTINAL v2 is a zero-cloud, on-premise AI video surveillance system designed for privacy-first, real-time security. It leverages state-of-the-art computer vision models for detection, tracking, and recognition, all running on local hardware.

## 🚀 Key Features

-   **Real-time AI Vision:**
    -   **Object Detection:** YOLO11 for high-speed person and object detection.
    -   **Multi-Object Tracking:** BoT-SORT for robust identity persistence.
    -   **Person Re-ID:** OSNet for cross-camera person matching.
    -   **Face Recognition:** InsightFace (ArcFace) for high-accuracy identification.
    -   **Weapon Detection:** Specialized YOLOv8 models for firearms and cold weapons.
-   **Intelligent Monitoring:**
    -   **Zone Management:** Polygon-based inclusion/exclusion zones with intrusion detection.
    -   **Anomaly Detection:** Loitering detection, crowd threshold monitoring, and movement-based violence detection.
-   **Modern Dashboard:**
    -   React-based SPA with real-time WebSocket updates.
    -   Low-latency MJPEG streaming and live event feed.
    -   Interactive zone editor and identity management.
-   **Security & Privacy:**
    -   JWT-based authentication and rate-limited API endpoints.
    -   On-premise storage (SQLite for dev, PostgreSQL for production).
    -   No cloud dependencies for core AI operations.

## 🏗️ System Architecture

SENTINAL v2 follows a decoupled, multi-process architecture:

1.  **Frontend (Dashboard):** React (Vite) + Zustand for state + Tailwind CSS (via components).
2.  **API (Backend):** FastAPI for orchestration, auth, and data management.
3.  **Engine (AI Pipeline):** Multi-threaded/Multi-process OpenCV pipelines per camera.
4.  **Storage:** SQLite/PostgreSQL for metadata, local filesystem for JPEG snapshots.

## 🛠️ Setup & Installation

### Prerequisites

-   Python 3.10+
-   Node.js 18+
-   NVIDIA GPU with CUDA 11.8+ (Highly Recommended)
-   C++ Build Tools (for some Python packages)

### 1. Clone & Prepare Environment
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt
# (Optional) For GPU support
pip install onnxruntime-gpu
```

### 2. Configure Settings
Copy `.env.example` to `.env` and update the `JWT_SECRET_KEY` and any camera URLs.

### 3. Install Frontend Dependencies
```powershell
cd dashboard
npm install
cd ..
```

## 🚥 Quick Start Commands

### Start All Services (Recommended)
You can run both the backend and frontend simultaneously.

**Backend:**
```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```powershell
cd dashboard
npm run dev
```

### Running Tests
The project includes a comprehensive test suite for API and Engine validation.

```powershell
# Run all tests
pytest

# Run specific performance benchmarks
pytest tests/test_performance.py

# Test Re-ID and Face Recognition
pytest tests/test_reid_face.py
```

## 📁 Project Structure

-   `api/`: FastAPI routers, middleware, and services.
-   `dashboard/`: React frontend application.
-   `engine/`: Core AI pipeline, vision modules, and camera management.
-   `data/`: Local storage for databases, snapshots, and logs.
-   `models/`: AI model weights (.pt, .onnx, .pth).
-   `tests/`: Integration, unit, and performance tests.

## 🛡️ License

Private / Proprietary. Refer to project documentation for usage rights.
