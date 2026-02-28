import sys
from pathlib import Path

# Provide absolute package resolution for imports in the backend referencing sentinal
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.core.config import settings
from backend.routers import health, events, video, zones, ws, cameras, stats
from backend.services.video_service import video_manager
from fastapi.staticfiles import StaticFiles
from pathlib import Path


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background SENTINAL engine
    video_manager.start()
    yield
    # Cleanup background engine 
    video_manager.stop()


app = FastAPI(title=settings.backend_title, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(events.router, tags=["Events"])
app.include_router(video.router, tags=["Video"])
app.include_router(zones.router, tags=["Zones"])
app.include_router(ws.router, tags=["WebSocket"])
app.include_router(cameras.router, tags=["Cameras"])
app.include_router(stats.router, tags=["Stats"])

# Serve snapshot images as static files
_snapshots_dir = Path("snapshots")
_snapshots_dir.mkdir(exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=str(_snapshots_dir)), name="snapshots")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
