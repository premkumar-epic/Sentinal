"""Shared pytest fixtures for SENTINAL v2 tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def mock_db_and_cameras(request):
    """
    Patch DB init, camera service startup, and directory creation
    so tests don't need real DB, cameras, or filesystem.

    Applied to all tests automatically via autouse=True.
    Gracefully skips patching for performance tests.
    """
    # Skip this fixture for performance tests that don't need mocking
    if hasattr(request, "node") and "performance" in str(request.node.nodeid):
        yield
        return

    # Only try patching if modules actually exist
    active_patches = []

    # Attempt to patch each module individually with error handling
    def try_patch(target, **kwargs):
        try:
            p = patch(target, **kwargs)
            active_patches.append(p)
            return p.__enter__()
        except (ImportError, AttributeError, ModuleNotFoundError):
            return None

    try_patch("engine.storage.db.init_db", new_callable=AsyncMock)
    try_patch("api.services.camera_service.camera_service.restore_cameras", new_callable=MagicMock)
    try_patch("api.services.camera_service.camera_service.stop_all", new_callable=MagicMock)
    try_patch("api.services.camera_service.camera_service.list_cameras", return_value=[])
    try_patch("api.services.camera_service.camera_service.add_camera", new_callable=MagicMock)
    try_patch("os.makedirs")

    try:
        yield
    finally:
        for p in reversed(active_patches):
            try:
                p.__exit__(None, None, None)
            except Exception:
                pass
