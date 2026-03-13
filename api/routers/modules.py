"""
SENTINAL v2 — Module Management API.
Endpoints for listing, enabling, disabling, and configuring detection modules.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.camera_service import camera_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/modules", tags=["Modules"])


class ModuleInfo(BaseModel):
    module_id: str
    display_name: str
    description: str
    requires_model: bool
    enabled: bool
    loaded: bool
    config: Dict[str, Any]


class ModuleUpdate(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


@router.get("", response_model=List[ModuleInfo])
async def list_modules():
    """List all available modules and their current status."""
    registry = camera_service.get_module_registry()
    if not registry:
        raise HTTPException(status_code=503, detail="Module registry not initialized")
    return registry.list_modules()


@router.get("/{module_id}", response_model=ModuleInfo)
async def get_module(module_id: str):
    """Get detailed status for a single module."""
    registry = camera_service.get_module_registry()
    if not registry:
        raise HTTPException(status_code=503, detail="Module registry not initialized")
    
    modules = registry.list_modules()
    for m in modules:
        if m["module_id"] == module_id:
            return m
            
    raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found")


@router.put("/{module_id}")
async def update_module(module_id: str, update: ModuleUpdate):
    """Enable/disable a module or update its configuration."""
    registry = camera_service.get_module_registry()
    if not registry:
        raise HTTPException(status_code=503, detail="Module registry not initialized")
    
    # 1. Update enabled state
    if update.enabled is not None:
        if update.enabled:
            success = registry.enable(module_id)
        else:
            success = registry.disable(module_id)
            
        if not success and update.enabled:
            raise HTTPException(status_code=500, detail=f"Failed to enable module '{module_id}'")

    # 2. Update config
    if update.config is not None:
        success = registry.update_module_config(module_id, update.config)
        if not success:
            raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found")
            
    return {"status": "success"}
