from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from config import AppConfig, VideoConfig, load_config
from sentinal.pipeline import SurveillancePipeline
from sentinal.utils.logging_utils import get_logger


logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SENTINALv1 surveillance engine")
    parser.add_argument(
        "--source",
        choices=["webcam", "video"],
        default="webcam",
        help="Video source type.",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to video file when using --source video.",
    )
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=0,
        help="Number of frames to skip between processing.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> AppConfig:
    cfg = load_config()
    video_cfg = VideoConfig(
        source_type=args.source,
        webcam_index=0,
        video_path=Path(args.path) if args.source == "video" and args.path else None,
        frame_skip=args.frame_skip,
    )
    cfg.video = video_cfg
    return cfg


def main() -> None:
    args = parse_args()
    try:
        config = build_config(args)
        pipeline = SurveillancePipeline(config)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to initialize pipeline: %s", exc)
        return

    try:
        for frame, _, _ in pipeline.frames():
            cv2.imshow("SENTINALv1", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except Exception as exc:  # noqa: BLE001
        logger.error("Error during main loop: %s", exc)
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

