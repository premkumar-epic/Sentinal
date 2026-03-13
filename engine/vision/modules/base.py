"""
SENTINAL v2 — Detection Module ABC + shared dataclasses.
All detection modules (weapon, PPE, anomaly, etc.) implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from engine.vision.detector import Detection
from engine.vision.tracker import Track


@dataclass
class FrameContext:
    """All data a module needs to process a single frame."""

    frame: np.ndarray
    detections: list[Detection]
    tracks: list[Track]
    global_ids: dict[int, str]
    cam_id: str
    frame_count: int
    zone_events: list = field(default_factory=list)


@dataclass
class ModuleDetection:
    """An extra detection produced by a module (e.g., PPE violation box)."""

    bbox: tuple[int, int, int, int]
    label: str
    confidence: float
    color_bgr: tuple[int, int, int] = (0, 140, 255)  # orange default


@dataclass
class ModuleResult:
    """Return value from a module's process() call."""

    module_id: str
    alerts: list[Any] = field(default_factory=list)
    detections: list[ModuleDetection] = field(default_factory=list)
    annotations: list[dict] = field(default_factory=list)


class DetectionModule(ABC):
    """
    Abstract base class for all SENTINAL detection modules.

    Each module has a lifecycle: load() -> process() -> unload().
    Modules that require a model file set requires_model=True.
    """

    @property
    @abstractmethod
    def module_id(self) -> str:
        """Unique identifier for this module (e.g., 'weapon', 'ppe')."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name shown in the dashboard."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of what this module does."""

    @property
    def requires_model(self) -> bool:
        """Whether this module needs a model file to function."""
        return False

    @property
    def is_loaded(self) -> bool:
        """Whether the module's resources (model, etc.) are currently loaded."""
        return self._loaded

    def __init__(self) -> None:
        self._loaded: bool = False
        self._config: dict = {}

    @abstractmethod
    def load(self) -> None:
        """Load model / initialize resources. Called when module is enabled."""

    @abstractmethod
    def unload(self) -> None:
        """Release model / free VRAM. Called when module is disabled."""

    @abstractmethod
    def process(self, ctx: FrameContext) -> ModuleResult:
        """Run detection on a single frame context. Must be thread-safe."""

    def get_config(self) -> dict:
        """Return current module configuration as a dict."""
        return dict(self._config)

    def update_config(self, new_config: dict) -> None:
        """Update module configuration. Subclasses override to apply changes."""
        self._config.update(new_config)
