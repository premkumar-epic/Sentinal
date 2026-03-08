import time
import unittest.mock as mock
import pytest
import cv2
import numpy as np
from engine.stream.source import VideoSource
from engine.config import settings

@pytest.fixture
def video_source():
    # Use a dummy URL and ID
    return VideoSource(url="rtsp://dummy", cam_id="test_cam")

def test_video_source_start_stop(video_source):
    """Test that start() starts the thread and stop() stops it."""
    with mock.patch("cv2.VideoCapture") as mock_vc:
        # Mock successful open
        mock_cap = mock_vc.return_value
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))

        video_source.start()
        assert video_source.is_alive() is True
        assert video_source._thread.is_alive() is True

        video_source.stop()
        assert video_source._thread.is_alive() is False

def test_video_source_reconnect_forever(video_source):
    """Test that VideoSource keeps retrying beyond the error threshold."""
    # Set a very low threshold and mock the wait to speed up the test
    settings.stream_reconnect_error_threshold = 2
    
    with mock.patch("cv2.VideoCapture") as mock_vc, \
         mock.patch.object(video_source._stop_event, "wait", return_value=False) as mock_wait:
        
        # Mock failed open
        mock_cap = mock_vc.return_value
        mock_cap.isOpened.return_value = False
        
        video_source.start()
        
        # Give it a moment to run several loops (mock_wait returns immediately)
        time.sleep(0.2)
        
        video_source.stop()
        
        # VideoCapture should have been called many times
        # retry 0: immediate try
        # retry 1: wait 2s, then try
        # retry 2: wait 4s, then try
        # retry 3: wait 8s, then try...
        # Since mock_wait doesn't wait, it should happen very fast.
        assert mock_vc.call_count > 3
        # Ensure it was still alive while retrying
        # (We can't easily check this after stop, but we can assume from logic)

def test_video_source_stop_cleanly(video_source):
    """Test that stop() wakes up the thread from sleep and exits."""
    with mock.patch("cv2.VideoCapture") as mock_vc:
        mock_cap = mock_vc.return_value
        mock_cap.isOpened.return_value = False # Force retry loop
        
        video_source.start()
        
        # Wait until it's in the retry loop (retry > 0)
        # We can't easily wait for 'retry > 0' without internal access, 
        # but 0.1s should be enough for the first failed attempt.
        time.sleep(0.1)
        
        start_time = time.time()
        video_source.stop()
        end_time = time.time()
        
        # Should stop quickly even if it was supposed to wait for seconds
        assert end_time - start_time < 2.0
        assert video_source._thread.is_alive() is False
