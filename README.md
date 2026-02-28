You are a senior AI computer vision engineer and Python architect.

We are building a production-ready AI surveillance MVP system.

PROJECT GOAL

Build a modular, scalable surveillance engine that:

Works with laptop webcam (real-time)

Works with uploaded CCTV video files (.mp4, .avi)

Performs real-time person detection using YOLOv8n

Performs multi-object tracking using ByteTrack

Detects zone intrusion using polygon logic

Logs alerts and saves snapshot images

Runs on CPU (no GPU dependency)

Has clean modular architecture

Is easily extendable later to RTSP/Hikvision cameras

No paid APIs

No cloud services

No unnecessary dependencies


FUNCTIONAL REQUIREMENTS

VideoSource module:

Accept mode: webcam or video file

Handle errors

Gracefully handle end-of-video

Provide get_frame() method

Thread-safe design

Detection module:

Use YOLOv8n

Detect only "person" class

Return bounding boxes in structured dictionary format

Load model once

Tracking module:

Integrate ByteTrack using ultralytics tracking mode

Maintain persistent object IDs

Return tracked objects with ID + bbox

Zone detection:

Accept polygon coordinates from config.py

Check if object center enters polygon

Trigger event only once per ID

Reset if object exits

Alert manager:

Log alerts to text file

Save frame snapshot to folder

Include timestamp + object ID

Avoid duplicate alerts

main.py:

Parse CLI arguments:
--source webcam
--source video --path file.mp4

Initialize all modules

Run processing loop

Draw bounding boxes + tracking IDs

Draw zone polygon

Trigger alerts

Exit on 'q'

Release resources properly

PERFORMANCE REQUIREMENTS

Must work smoothly on CPU

Use yolov8n only

Add optional frame skipping

Handle exceptions without crashing

Use logging module (not print)

CODING RULES

Use type hints

Use OOP design

Clean separation of concerns

No global variables

Add docstrings

Production-style error handling

Avoid unnecessary comments

Write clean and scalable code

IMPORTANT

We will build this file by file.

Do NOT generate entire project in one response.

First:

Generate the folder structure.

Explain module responsibilities.

Then ask me which file to generate first.

Wait for my confirmation before generating files.