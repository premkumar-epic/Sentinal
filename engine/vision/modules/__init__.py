"""
SENTINAL v2 — Modular detection system.
Each detection module implements DetectionModule ABC and is managed by ModuleRegistry.
"""

from engine.vision.modules.base import DetectionModule, FrameContext, ModuleResult
from engine.vision.modules.registry import ModuleRegistry

__all__ = ["DetectionModule", "FrameContext", "ModuleResult", "ModuleRegistry"]
