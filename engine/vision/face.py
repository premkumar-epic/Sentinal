"""
SENTINAL v2 — Vision: Face Recognition
Wraps InsightFace ArcFace for face detection, recognition, and enrollment.
Thread-safe with graceful fallback if insightface not installed.
"""

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from engine.config import settings

logger = logging.getLogger(__name__)


@dataclass
class FaceResult:
    """Result of face detection and recognition on a single face."""

    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    embedding: np.ndarray  # 512-d ArcFace embedding
    quality_score: float  # 0.0–1.0 (from InsightFace det_score)
    name: Optional[str]  # None if unknown
    global_id: Optional[str]  # matched identity global_id if known


class FaceRecognizer:
    """
    Face detection, recognition, and enrollment using InsightFace buffalo_l model.

    Thread-safe storage of known identities with cosine similarity matching.
    Gracefully degrades if insightface is not installed.
    """

    def __init__(self, model_pack: str = "buffalo_l") -> None:
        """
        Initialize FaceRecognizer with InsightFace model.

        Args:
            model_pack: InsightFace model pack name (default: "buffalo_l")

        Sets up GPU context (ctx_id=0) if available, falls back to CPU (ctx_id=-1).
        Logs WARNING if insightface not installed; sets self._app = None for graceful fallback.
        """
        self._app = None
        self._quality_threshold = settings.face_quality_threshold
        self._lock = threading.RLock()
        self._clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        self.known_embeddings: dict[str, tuple[str, np.ndarray]] = {}

        try:
            import insightface
            from insightface.app import FaceAnalysis

            try:
                # Try GPU first
                self._app = FaceAnalysis(name=model_pack)
                self._app.prepare(ctx_id=0)
                logger.info("FaceRecognizer initialized with GPU (ctx_id=0)")
            except Exception as e:
                # Fallback to CPU
                logger.warning("GPU context failed (%s), falling back to CPU", e)
                self._app = FaceAnalysis(name=model_pack)
                self._app.prepare(ctx_id=-1)
                logger.info("FaceRecognizer initialized with CPU (ctx_id=-1)")

        except ImportError as e:
            logger.warning("insightface not installed: %s. Face recognition disabled.", e)
            self._app = None

    def _preprocess_crop(self, crop: np.ndarray) -> np.ndarray:
        """
        Enhance image quality using CLAHE on the L channel of LAB color space.

        Args:
            crop: BGR image array

        Returns:
            CLAHE-enhanced BGR image
        """
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        cl = self._clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

    def analyze(self, frame: np.ndarray) -> list[FaceResult]:
        """
        Detect and recognize faces in a frame.

        Args:
            frame: BGR image array (H, W, 3)

        Returns:
            List of FaceResult objects with detection boxes, embeddings, quality scores,
            and matched identity names/global_ids (or None if unknown).

        Returns empty list if insightface not installed.
        """
        if self._app is None:
            return []

        # Apply CLAHE preprocessing to the entire frame
        frame = self._preprocess_crop(frame)

        try:
            # Detect all faces in frame
            faces = self._app.get(frame)
        except Exception as e:
            logger.error("Face detection failed: %s", e)
            return []

        results: list[FaceResult] = []

        for face in faces:
            # Extract bbox and compute area
            x1, y1, x2, y2 = face.bbox
            w, h = x2 - x1, y2 - y1
            area = w * h
            det_score = float(face.det_score)

            # Quality gate: check area and confidence (minimum 0.6)
            threshold = max(self._quality_threshold, 0.6)
            img_h, img_w = frame.shape[:2]
            # Reject tiny faces (< 50×50) and faces clipped by frame edges
            face_clipped = x1 < 0 or y1 < 0 or x2 > img_w or y2 > img_h
            if area < 2500 or det_score < threshold or face_clipped:
                logger.debug(
                    "Face skipped: det_score=%.3f area=%d clipped=%s",
                    det_score, int(area), face_clipped,
                )
                continue

            # Multi-crop margin (5% padding) for context
            pad = int(0.05 * max(h, w))
            y1_pad = max(0, int(y1) - pad)
            y2_pad = min(img_h, int(y2) + pad)
            x1_pad = max(0, int(x1) - pad)
            x2_pad = min(img_w, int(x2) + pad)
            _crop = frame[y1_pad:y2_pad, x1_pad:x2_pad]  # Extracted for context as required

            # Extract 512-d normalized embedding
            embedding = face.normed_embedding.astype(np.float32)

            # Match against known embeddings by cosine similarity — find BEST match, not first
            matched_name = None
            matched_global_id = None
            best_similarity = 0.0
            _FACE_MATCH_THRESHOLD = settings.face_match_threshold

            with self._lock:
                for global_id, (name, known_embedding) in self.known_embeddings.items():
                    similarity = float(np.dot(embedding, known_embedding))
                    if similarity > _FACE_MATCH_THRESHOLD and similarity > best_similarity:
                        best_similarity = similarity
                        matched_name = name
                        matched_global_id = global_id

                if matched_name is not None:
                    logger.debug(
                        "Face match: name=%s gid=%s score=%.3f",
                        matched_name,
                        matched_global_id,
                        best_similarity,
                    )

            # Extract final bbox for result
            bbox = (int(x1), int(y1), int(x2), int(y2))

            results.append(
                FaceResult(
                    bbox=bbox,
                    embedding=embedding,
                    quality_score=det_score,
                    name=matched_name,
                    global_id=matched_global_id,
                )
            )

        return results

    def enroll(self, name: str, face_image: np.ndarray, global_id: Optional[str] = None, loop: Optional[asyncio.AbstractEventLoop] = None) -> str:
        """
        Enroll a new person by detecting their face in an image and storing the embedding.

        Args:
            name: Human-readable name for this identity
            face_image: BGR image array containing one or more faces
            global_id: Optional UUID string for the identity. If None, one is generated.
            loop: Optional event loop to use for async DB operations.

        Returns:
            UUID string (global_id) for the enrolled identity

        Raises:
            ValueError: If no face detected in image
            RuntimeError: If insightface not installed

        Spawns daemon thread to persist embedding to database and save snapshot asynchronously.
        """
        if self._app is None:
            raise RuntimeError("insightface not installed")

        try:
            faces = self._app.get(face_image)
        except Exception as e:
            logger.error("Face detection in enrollment image failed: %s", e)
            raise ValueError("No face detected in enrollment image") from e

        if not faces:
            raise ValueError("No face detected in enrollment image")

        # Use highest-quality face (max det_score)
        best_face = max(faces, key=lambda f: f.det_score)
        embedding = best_face.normed_embedding.astype(np.float32)

        # Extract bbox for cropping
        x1, y1, x2, y2 = best_face.bbox
        h, w = face_image.shape[:2]
        # Pad crop slightly
        pad = int(0.1 * max(y2-y1, x2-x1))
        x1_p, y1_p = max(0, int(x1-pad)), max(0, int(y1-pad))
        x2_p, y2_p = min(w, int(x2+pad)), min(h, int(y2+pad))
        face_crop = face_image[y1_p:y2_p, x1_p:x2_p]

        # Generate UUID for this identity if not provided
        if global_id is None:
            global_id = str(uuid.uuid4())

        # Store in memory with lock
        with self._lock:
            self.known_embeddings[global_id] = (name, embedding)

        # Persist to database and save snapshot in background daemon thread
        def _persist_to_db() -> None:
            try:
                # 1. Save snapshot
                from pathlib import Path
                snap_dir = Path(settings.snapshots_dir) / "identities"
                snap_dir.mkdir(parents=True, exist_ok=True)
                snap_path = str(snap_dir / f"{global_id}.jpg")
                cv2.imwrite(snap_path, face_crop, [cv2.IMWRITE_JPEG_QUALITY, 90])

                # 2. Persist to DB
                from engine.storage.db import upsert_identity
                nonlocal loop
                if loop is None:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        logger.warning("No event loop available for face enrollment DB persist")
                        return
                _loop = loop
                future = asyncio.run_coroutine_threadsafe(
                    upsert_identity(global_id, name, embedding.tobytes()), _loop
                )
                future.result(timeout=10)
                logger.info("Enrolled identity: global_id=%s, name=%s, snapshot=%s", global_id, name, snap_path)
            except Exception as e:
                logger.error("Failed to persist enrollment: %s", e)

        thread = threading.Thread(target=_persist_to_db, daemon=True)
        thread.start()

        return global_id

    def load_known_from_db(self, identities: list[dict]) -> None:
        """
        Load all known identities from database.

        Args:
            identities: List of dicts with keys: global_id, name, embedding (bytes)

        Skips rows where embedding is None or empty.
        Thread-safe using internal lock.
        """
        with self._lock:
            for row in identities:
                global_id = row.get("global_id")
                name = row.get("name")
                embedding_bytes = row.get("embedding")

                # Skip invalid rows
                if not global_id or not embedding_bytes:
                    continue

                try:
                    # Deserialize from bytes blob
                    embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                    self.known_embeddings[global_id] = (name, embedding)
                except Exception as e:
                    logger.warning("Failed to deserialize embedding for %s: %s", global_id, e)

        logger.info("Loaded %d known identities from database", len(self.known_embeddings))

    def update_known(self, global_id: str, name: str, embedding: np.ndarray) -> None:
        """
        Update or add a known identity with a new embedding.

        Args:
            global_id: UUID string for the identity
            name: Human-readable name
            embedding: 512-d float32 numpy array

        Thread-safe using internal lock.
        """
        embedding_f32 = embedding.astype(np.float32)
        with self._lock:
            self.known_embeddings[global_id] = (name, embedding_f32)
