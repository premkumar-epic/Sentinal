import os
import sys
import time
import urllib.request
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from Core_AI.config import load_config
from Core_AI.pipeline import SurveillancePipeline

VIDEO_URL = "https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4"
VIDEO_PATH = "sample_video.mp4"

def download_video():
    if not os.path.exists(VIDEO_PATH):
        print(f"Downloading sample video from {VIDEO_URL}...")
        urllib.request.urlretrieve(VIDEO_URL, VIDEO_PATH)
        print("Download complete.")

def run_benchmark():
    download_video()
    
    # Configure Pipeline for Benchmark
    config = load_config()
    config.video.source_type = "video"
    config.video.video_path = str(Path(VIDEO_PATH).absolute())
    config.video.frame_skip = 0 # measure raw throughput
    
    # Disable alerts and DB for benchmark purely profiling the AI
    config.alert.database_url = "" 
    
    print(f"Initializing Surveillance Pipeline with {config.model.model_name}...")
    pipeline = SurveillancePipeline(config)
    
    print("Starting benchmark loop...")
    start_time = time.time()
    frame_count = 0
    unique_ids = set()
    
    for frame, tracks, events in pipeline.frames():
        frame_count += 1
        for t in tracks:
            # stable_id added by TrackIdStitcher
            unique_ids.add(t.get("stable_id", 0))
        
        if frame_count % 50 == 0:
            elapsed = time.time() - start_time
            print(f"Processed {frame_count} frames... (Avg FPS: {frame_count/elapsed:.2f})")
            
    total_time = time.time() - start_time
    avg_fps = frame_count / max(total_time, 1e-5)
    
    print("\n" + "="*40)
    print("        SENTINALv1 BENCHMARK")
    print("="*40)
    print(f"Video Path:    {VIDEO_PATH}")
    print(f"Total Frames:  {frame_count}")
    print(f"Total Time:    {total_time:.2f} seconds")
    print(f"Average FPS:   {avg_fps:.2f} FPS")
    print(f"Unique Tracks: {len(unique_ids)} identities assigned")
    print("="*40 + "\n")
    
    with open("benchmark_results.md", "w") as f:
        f.write("# SENTINALv1 Benchmark Results\n\n")
        f.write(f"- **Frames Processed:** {frame_count}\n")
        f.write(f"- **Total Runtime Time:** {total_time:.2f} seconds\n")
        f.write(f"- **Average throughput:** {avg_fps:.2f} FPS\n")
        f.write(f"- **Unique IDs generated:** {len(unique_ids)} (Lower indicates stable Re-ID without ID flickering)\n")

if __name__ == "__main__":
    run_benchmark()
