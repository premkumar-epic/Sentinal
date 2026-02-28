from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Optional

# Allow importing Core_AI from the parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

import cv2
from PyQt5 import QtCore, QtGui, QtWidgets

from Core_AI.config import AppConfig, VideoConfig, load_config
from Core_AI.pipeline import SurveillancePipeline
from Core_AI.utils.logging_utils import get_logger


logger = get_logger(__name__)


class VideoThread(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)

    def __init__(self, pipeline: SurveillancePipeline) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._running = False

    def run(self) -> None:
        self._running = True
        try:
            for frame, _, _ in self._pipeline.frames():
                if not self._running:
                    break
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                qt_image = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                self.frame_ready.emit(qt_image)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error in video thread: %s", exc)

    def stop(self) -> None:
        self._running = False
        self.wait()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SENTINALv1")
        self._video_label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self._start_button = QtWidgets.QPushButton("Start")
        self._stop_button = QtWidgets.QPushButton("Stop")
        self._source_combo = QtWidgets.QComboBox()
        self._source_combo.addItems(["webcam", "video"])
        self._file_button = QtWidgets.QPushButton("Select Video...")

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(self._source_combo)
        controls.addWidget(self._file_button)
        controls.addWidget(self._start_button)
        controls.addWidget(self._stop_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._video_label)
        layout.addLayout(controls)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._video_path: Optional[Path] = None
        self._thread: Optional[VideoThread] = None

        self._file_button.clicked.connect(self._select_video)
        self._start_button.clicked.connect(self._start_pipeline)
        self._stop_button.clicked.connect(self._stop_pipeline)

    def _select_video(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select video file")
        if path:
            self._video_path = Path(path)
            self._source_combo.setCurrentText("video")

    def _start_pipeline(self) -> None:
        cfg = load_config()
        # Only override source/path — all other video config (frame_skip, resolution) inherits from .env
        source_type = self._source_combo.currentText()
        cfg.video.source_type = source_type
        cfg.video.video_path = self._video_path if source_type == "video" else None
        pipeline = SurveillancePipeline(cfg)
        self._thread = VideoThread(pipeline)
        self._thread.frame_ready.connect(self._update_frame)
        self._thread.start()

    def _stop_pipeline(self) -> None:
        if self._thread is not None:
            self._thread.stop()
            self._thread = None

    @QtCore.pyqtSlot(QtGui.QImage)
    def _update_frame(self, image: QtGui.QImage) -> None:
        pixmap = QtGui.QPixmap.fromImage(image)
        self._video_label.setPixmap(pixmap.scaled(self._video_label.size(), QtCore.Qt.KeepAspectRatio))


def main() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.resize(960, 540)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

