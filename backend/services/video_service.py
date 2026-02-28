import threading
import time
import cv2
from typing import Optional, Generator

from config import load_config
from sentinal.pipeline import SurveillancePipeline

class VideoStreamManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VideoStreamManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        self.initialized = True
        self.config = load_config()
        self.pipeline = SurveillancePipeline(self.config)
        self.latest_frame: Optional[bytes] = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_pipeline, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _run_pipeline(self):
        for display_frame, tracks, events in self.pipeline.frames():
            if not self.running:
                break
                
            # Encode frame as JPEG for MJPEG stream
            ret, buffer = cv2.imencode('.jpg', display_frame)
            if ret:
                with self.lock:
                    self.latest_frame = buffer.tobytes()
            time.sleep(0.001)

    def generate_mjpeg(self, camera_id: str) -> Generator[bytes, None, None]:
        """Yield frames in MJPEG format for the given camera."""
        while self.running:
            with self.lock:
                frame = self.latest_frame
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.03)

video_manager = VideoStreamManager()
