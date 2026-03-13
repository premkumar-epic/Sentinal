"""
SENTINAL v2 — Module Registry.
Manages detection module lifecycle: registration, enable/disable, persistence.
Thread-safe — pipeline threads call get_enabled_modules() concurrently.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional

import torch

from engine.vision.modules.base import DetectionModule

logger = logging.getLogger(__name__)

_MODULES_JSON = Path("data/modules.json")


class ModuleRegistry:
    """
    Central registry for all detection modules.

    Handles:
    - Registration of module instances
    - Enable/disable with model load/unload lifecycle
    - Persistence of enabled state to data/modules.json
    - Thread-safe access for pipeline iteration
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # module_id -> DetectionModule instance
        self._modules: dict[str, DetectionModule] = {}
        # module_id -> bool (enabled state)
        self._enabled: dict[str, bool] = {}
        # Persisted state loaded on init
        self._persisted_state: dict = self._load_persisted_state()

    def register(self, module: DetectionModule, enabled_default: bool = False) -> None:
        """Register a module. Uses persisted state if available, else enabled_default."""
        with self._lock:
            mid = module.module_id
            self._modules[mid] = module
            # Use persisted state if it exists, otherwise use default
            should_enable = self._persisted_state.get(mid, {}).get("enabled", enabled_default)
            # Restore persisted config
            persisted_config = self._persisted_state.get(mid, {}).get("config")
            if persisted_config:
                module.update_config(persisted_config)
            self._enabled[mid] = False  # Start disabled, then enable if needed
            if should_enable:
                self._do_enable(mid)
            logger.info(
                "ModuleRegistry: registered '%s' (enabled=%s, requires_model=%s)",
                mid, self._enabled[mid], module.requires_model,
            )

    def enable(self, module_id: str) -> bool:
        """Enable a module (loads its model). Returns True on success."""
        with self._lock:
            if module_id not in self._modules:
                logger.warning("ModuleRegistry: unknown module '%s'", module_id)
                return False
            if self._enabled.get(module_id):
                return True  # Already enabled
            success = self._do_enable(module_id)
            if success:
                self._persist()
            return success

    def disable(self, module_id: str) -> bool:
        """Disable a module (unloads model, frees VRAM). Returns True on success."""
        with self._lock:
            if module_id not in self._modules:
                return False
            if not self._enabled.get(module_id):
                return True  # Already disabled
            self._do_disable(module_id)
            self._persist()
            return True

    def is_enabled(self, module_id: str) -> bool:
        """Check if a module is currently enabled."""
        with self._lock:
            return self._enabled.get(module_id, False)

    def get_module(self, module_id: str) -> Optional[DetectionModule]:
        """Get a module instance by ID."""
        with self._lock:
            return self._modules.get(module_id)

    def get_enabled_modules(self) -> list[DetectionModule]:
        """Return a snapshot list of all enabled modules (safe for pipeline iteration)."""
        with self._lock:
            return [
                self._modules[mid]
                for mid, enabled in self._enabled.items()
                if enabled and self._modules[mid].is_loaded
            ]

    def list_modules(self) -> list[dict]:
        """Return info dicts for all registered modules."""
        with self._lock:
            result = []
            for mid, module in self._modules.items():
                result.append({
                    "module_id": mid,
                    "display_name": module.display_name,
                    "description": module.description,
                    "requires_model": module.requires_model,
                    "enabled": self._enabled.get(mid, False),
                    "loaded": module.is_loaded,
                    "config": module.get_config(),
                })
            return result

    def update_module_config(self, module_id: str, config: dict) -> bool:
        """Update a module's config and persist. Returns True on success."""
        with self._lock:
            module = self._modules.get(module_id)
            if module is None:
                return False
            module.update_config(config)
            self._persist()
            return True

    def _do_enable(self, module_id: str) -> bool:
        """Internal: load module and mark as enabled. Must hold _lock."""
        module = self._modules[module_id]
        try:
            module.load()
            self._enabled[module_id] = True
            logger.info("ModuleRegistry: enabled '%s'", module_id)
            return True
        except Exception as exc:
            logger.error("ModuleRegistry: failed to enable '%s': %s", module_id, exc)
            self._enabled[module_id] = False
            return False

    def _do_disable(self, module_id: str) -> None:
        """Internal: unload module and mark as disabled. Must hold _lock."""
        module = self._modules[module_id]
        try:
            module.unload()
        except Exception as exc:
            logger.error("ModuleRegistry: error unloading '%s': %s", module_id, exc)
        self._enabled[module_id] = False
        # Free VRAM
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("ModuleRegistry: disabled '%s'", module_id)

    def _persist(self) -> None:
        """Save enabled state + config to data/modules.json."""
        _MODULES_JSON.parent.mkdir(parents=True, exist_ok=True)
        state = {}
        for mid, module in self._modules.items():
            state[mid] = {
                "enabled": self._enabled.get(mid, False),
                "config": module.get_config(),
            }
        try:
            _MODULES_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("ModuleRegistry: persist failed: %s", exc)

    @staticmethod
    def _load_persisted_state() -> dict:
        """Load persisted state from data/modules.json."""
        if not _MODULES_JSON.exists():
            return {}
        try:
            return json.loads(_MODULES_JSON.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("ModuleRegistry: could not load persisted state: %s", exc)
            return {}
