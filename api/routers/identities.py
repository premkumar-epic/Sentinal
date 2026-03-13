"""
SENTINAL v2 — API Router: Identities
Handles identity management, name updates, and face enrollment.
"""

import logging
import cv2
import numpy as np
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Response
from pydantic import BaseModel

from engine.storage.db import get_identities, update_identity_name, delete_identity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/identities", tags=["identities"])


class IdentityResponse(BaseModel):
    """Schema for identity details returned to the client."""
    global_id: str
    name: Optional[str]
    last_seen: Optional[str]
    last_cam: Optional[str]
    sighting_count: int
    enrolled_at: Optional[str]


class IdentityUpdate(BaseModel):
    """Schema for updating an identity's human-readable name."""
    name: str


@router.get("", response_model=List[IdentityResponse])
async def list_identities() -> List[IdentityResponse]:
    """
    Retrieve all known identities from the database.

    Returns:
        A list of IdentityResponse objects.
    """
    identities = await get_identities()
    return [IdentityResponse(**i) for i in identities]


@router.put("/{global_id}")
async def update_identity(global_id: str, body: IdentityUpdate) -> dict:
    """
    Update the display name of a specific identity.
    Also propagates the change to the in-memory FaceRecognizer so
    the live preview reflects the updated name immediately.
    """
    success = await update_identity_name(global_id, body.name)
    if not success:
        raise HTTPException(status_code=404, detail="Identity not found")

    # Propagate name change to in-memory face recognizer singleton
    try:
        from api.services.camera_service import _get_face_recognizer
        face = _get_face_recognizer()
        if face is not None:
            with face._lock:
                if global_id in face.known_embeddings:
                    _name_old, emb = face.known_embeddings[global_id]
                    face.known_embeddings[global_id] = (body.name, emb)
    except Exception as exc:
        logger.warning("Could not update in-memory face name: %s", exc)

    return {"global_id": global_id, "name": body.name, "updated": True}


@router.post("/{global_id}/enroll")
async def enroll_identity(
    global_id: str,
    name: str = Form(""),
    file: UploadFile = File(...)
) -> dict:
    """
    Enroll a face for an existing identity using an uploaded image.
    Uses the path global_id so the enrollment is linked to the correct person.
    """
    # Read file bytes
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Use the shared singleton from camera_service (not a local instance)
    from api.services.camera_service import _get_face_recognizer
    face = _get_face_recognizer()
    if face is None:
        raise HTTPException(status_code=503, detail="Face recognition not available")

    try:
        result_global_id = face.enroll(name, image, global_id=global_id)
        return {"global_id": result_global_id, "name": name, "enrolled": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Face recognition not available")


@router.delete("/{global_id}")
async def remove_identity(global_id: str) -> Response:
    """
    Delete an identity from the database and remove its snapshot file.
    """
    success = await delete_identity(global_id)
    if not success:
        raise HTTPException(status_code=404, detail="Identity not found")

    # Also remove snapshot file if it exists
    from pathlib import Path
    from engine.config import settings
    snap_path = Path(settings.snapshots_dir) / "identities" / f"{global_id}.jpg"
    if snap_path.exists():
        try:
            snap_path.unlink()
        except Exception as e:
            logger.error("Failed to delete snapshot %s: %s", snap_path, e)

    return Response(status_code=204)
