"""
SENTINAL v2 — Launcher
Helper for launching camera processes without pickling issues.
"""

import multiprocessing
import logging

logger = logging.getLogger(__name__)

def run_pipeline_process(cam_id: str, url: str, alert_queue, kwargs: dict):
    """
    Isolated entry point for the camera process.
    """
    try:
        # Import inside to avoid top-level dependencies in the parent process
        from engine.pipeline import CameraPipeline
        
        pipeline = CameraPipeline(
            cam_id=cam_id,
            source_url=url,
            alert_queue=alert_queue,
            **kwargs
        )
        pipeline.start_sync()
    except Exception as e:
        print(f"CRITICAL: Camera process '{cam_id}' failed: {e}")
        import traceback
        traceback.print_exc()
