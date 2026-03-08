"""
SENTINAL v2 — API Router: Identities
Handles identity management, name updates, and face enrollment.
"""

import cv2
import numpy as np
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Response
from pydantic import BaseModel

from engine.storage.db import get_identities, update_identity_name, delete_identity

router = APIRouter(prefix="/api/identities", tags=["identities"])

# Module-level singleton for FaceRecognizer
_face_recognizer: Optional[object] = None


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

    Args:
        global_id: The unique identifier for the identity.
        body: The update data containing the new name.

    Returns:
        A confirmation dictionary with the updated name.

    Raises:
        HTTPException: 404 if the identity is not found.
    """
    success = await update_identity_name(global_id, body.name)
    if not success:
        raise HTTPException(status_code=404, detail="Identity not found")

    return {"global_id": global_id, "name": body.name, "updated": True}


@router.post("/{global_id}/enroll")
async def enroll_identity(
    global_id: str,
    name: str = Form(...),
    file: UploadFile = File(...)
) -> dict:
    """
    Enroll a new face identity using an uploaded image.

    Args:
        global_id: The ID in the path (standardised route, though enrollment generates a new UUID).
        name: The human-readable name for this identity.
        file: The image file containing the face to enroll.

    Returns:
        A dictionary containing the new global_id and enrollment status.

    Raises:
        HTTPException: 400 if the image is invalid or no face is detected.
        HTTPException: 503 if face recognition services are unavailable.
    """
    global _face_recognizer

    # Read file bytes
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Lazy-import FaceRecognizer
    if _face_recognizer is None:
        try:
            from engine.vision.face import FaceRecognizer
            _face_recognizer = FaceRecognizer()
        except ImportError:
            raise HTTPException(status_code=503, detail="Face recognition not available")

    try:
        # Call the singleton instance (ignoring path global_id as per enrollment spec)
        result_global_id = _face_recognizer.enroll(name, image)
        return {"global_id": result_global_id, "name": name, "enrolled": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="Face recognition not available")


@router.delete("/{global_id}")
async def remove_identity(global_id: str) -> Response:
    """
    Delete an identity from the database.

    Args:
        global_id: The unique identifier to delete.

    Returns:
        A 204 No Content response on success.

    Raises:
        HTTPException: 404 if the identity is not found.
    """
    success = await delete_identity(global_id)
    if not success:
        raise HTTPException(status_code=404, detail="Identity not found")

    return Response(status_code=204)
