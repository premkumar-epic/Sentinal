"""
SENTINAL v2 — Person Re-Identification (ReID) Engine
Handles global tracking across multiple cameras using deep features.
"""

import logging
import os
import threading
import time
import uuid
from typing import Dict, Tuple

import cv2
import faiss
import numpy as np
import torch

try:
    import torchreid
except ImportError:
    torchreid = None

from engine.config import settings


class ReIDEngine:
    """
    Engine for extracting and matching person re-identification embeddings.
    Uses OSNet-AIN model for feature extraction and FAISS for similarity search.
    """

    def __init__(self, model_path: str) -> None:
        """
        Initialize the ReID engine, load the model, and setup state.

        Args:
            model_path: Path to the OSNet-AIN model weights.
        """
        self.logger = logging.getLogger("engine.vision.reid")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._lock = threading.RLock()

        # Model initialization
        self.model = None
        if torchreid is not None:
            try:
                self.model = torchreid.models.build_model(
                    name="osnet_ain_x1_0", num_classes=1
                )
                if os.path.exists(model_path):
                    torchreid.utils.load_pretrained_weights(self.model, model_path)
                    self.logger.info(f"Loaded ReID model from {model_path}")
                else:
                    self.logger.warning(
                        f"ReID model path {model_path} not found. Using uninitialized weights."
                    )
                self.model.to(self.device)
                self.model.eval()
            except Exception as e:
                self.logger.error(f"Failed to initialize torchreid model: {e}")
                self.model = None
        else:
            self.logger.warning("torchreid not installed. ReID will use random embeddings.")

        # State initialization
        with self._lock:
            # FAISS Index for similarity search (Inner Product for cosine similarity on normalized vectors)
            self.gallery = faiss.IndexFlatIP(512)
            # Maps FAISS index position -> global_id
            self.id_map: Dict[int, str] = {}
            # Maps global_id -> current average embedding (normalized)
            self.embeddings_store: Dict[str, np.ndarray] = {}
            # Maps (cam_id, track_id) -> global_id
            self.local_to_global: Dict[Tuple[str, int], str] = {}
            # Maps global_id -> (embedding, expire_time)
            self.lost_pool: Dict[str, Tuple[np.ndarray, float]] = {}
            # Maps global_id -> last_seen timestamp (for gallery TTL)
            self._gallery_timestamps: Dict[str, float] = {}

    def extract_embedding(self, crop: np.ndarray) -> np.ndarray:
        """
        Extract a 512-dimensional normalized embedding from a BGR image crop.

        Args:
            crop: BGR image crop as a numpy array.

        Returns:
            A normalized 512-d float32 vector.
        """
        if self.model is None:
            # Fallback to normalized random vector
            vec = np.random.randn(512).astype(np.float32)
            return vec / np.linalg.norm(vec)

        # Preprocessing
        processed = self._preprocess(crop)

        # Normalize with ImageNet stats
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        processed = (processed.astype(np.float32) / 255.0 - mean) / std

        # Convert to tensor: (H, W, C) -> (C, H, W) -> (1, C, H, W)
        tensor = torch.from_numpy(processed.transpose(2, 0, 1)).unsqueeze(0).to(self.device)

        with torch.no_grad():
            features = self.model(tensor)
            embedding = features.cpu().numpy().flatten().astype(np.float32)

        # L2 Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def get_or_create_global_id(
        self, local_cam_id: str, local_track_id: int, embedding: np.ndarray
    ) -> str:
        """
        Retrieve existing global ID or assign a new one based on similarity.

        Args:
            local_cam_id: Camera identifier.
            local_track_id: Local track identifier from the camera's tracker.
            embedding: The 512-d normalized embedding for the current crop.

        Returns:
            The assigned global_id string.
        """
        with self._lock:
            # 1. Check if we already have a mapping for this (cam, track)
            key = (local_cam_id, local_track_id)
            if key in self.local_to_global:
                global_id = self.local_to_global[key]
                self.update_embedding(global_id, embedding)
                self._log_match_event(global_id, 1.0, False, local_cam_id, local_track_id)
                return global_id

            # 2. Clean expired entries from lost_pool
            now = time.time()
            self.lost_pool = {
                gid: (emb, exp) for gid, (emb, exp) in self.lost_pool.items() if exp > now
            }

            # 3. Search lost_pool by cosine similarity > 0.80
            best_lost_gid = None
            max_lost_sim = -1.0
            for gid, (stored_emb, _) in self.lost_pool.items():
                sim = np.dot(stored_emb, embedding)
                if sim > 0.80 and sim > max_lost_sim:
                    max_lost_sim = sim
                    best_lost_gid = gid

            if best_lost_gid:
                # Restore from lost_pool
                self.local_to_global[key] = best_lost_gid
                self.lost_pool.pop(best_lost_gid)
                # Update timestamp
                self._gallery_timestamps[best_lost_gid] = now
                self._log_match_event(best_lost_gid, max_lost_sim, False, local_cam_id, local_track_id)
                return best_lost_gid

            # 4. Search FAISS gallery
            if self.gallery.ntotal > 0:
                # faiss search expects (n, d)
                query = embedding.reshape(1, -1).astype(np.float32)
                similarities, indices = self.gallery.search(query, 1)

                if similarities[0][0] > 0.80:
                    idx = int(indices[0][0])
                    global_id = self.id_map.get(idx)
                    if global_id:
                        self.local_to_global[key] = global_id
                        # Update timestamp
                        self._gallery_timestamps[global_id] = now
                        self.update_embedding(global_id, embedding)
                        self._log_match_event(global_id, similarities[0][0], False, local_cam_id, local_track_id)
                        return global_id

            # 5. Create new global_id
            new_gid = str(uuid.uuid4())
            self.local_to_global[key] = new_gid
            self.embeddings_store[new_gid] = embedding
            self._gallery_timestamps[new_gid] = now

            # Rebuild index to include new embedding
            self._rebuild_index()
            self._log_match_event(new_gid, 0.0, True, local_cam_id, local_track_id)

            return new_gid

    def update_embedding(self, global_id: str, new_embedding: np.ndarray) -> None:
        """
        Update the stored embedding for a global_id using EMA.

        Args:
            global_id: The global identifier.
            new_embedding: The new normalized embedding vector.
        """
        with self._lock:
            if global_id in self.embeddings_store:
                stored = self.embeddings_store[global_id]
                # EMA update: 95% stored, 5% new
                updated = 0.95 * stored + 0.05 * new_embedding
                # L2-normalize
                norm = np.linalg.norm(updated)
                if norm > 0:
                    updated = updated / norm
                self.embeddings_store[global_id] = updated
                # Update timestamp
                self._gallery_timestamps[global_id] = time.time()

                # Rebuild FAISS index
                self._rebuild_index()
            else:
                # Should not happen if called correctly, but for safety:
                self.embeddings_store[global_id] = new_embedding
                self._gallery_timestamps[global_id] = time.time()
                self._rebuild_index()

    def move_to_lost(self, global_id: str) -> None:
        """
        Handle a person leaving the view of a camera.

        Args:
            global_id: The global identifier of the person.
        """
        with self._lock:
            # Remove all local mappings to this global_id
            keys_to_remove = [k for k, v in self.local_to_global.items() if v == global_id]
            for k in keys_to_remove:
                del self.local_to_global[k]

            # Add to lost_pool with 30s TTL
            if global_id in self.embeddings_store:
                emb = self.embeddings_store[global_id]
                self.lost_pool[global_id] = (emb, time.time() + 30.0)

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        """
        Apply CLAHE and resize for OSNet input.

        Args:
            crop: BGR image crop.

        Returns:
            Preprocessed BGR image.
        """
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        crop = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        crop = cv2.resize(crop, (128, 256))  # OSNet input size
        return crop

    def _rebuild_index(self) -> None:
        """
        Rebuild the FAISS index from the embeddings_store.
        Evicts entries from gallery_timestamps where time.time() - last_seen > 300 (5 min TTL).
        Must be called within self._lock.
        """
        now = time.time()
        # Evict stale gallery entries (TTL = 300 seconds)
        stale_gids = [
            gid for gid, ts in self._gallery_timestamps.items()
            if now - ts > 300
        ]
        for gid in stale_gids:
            self._gallery_timestamps.pop(gid, None)
            self.embeddings_store.pop(gid, None)
            keys_to_remove = [k for k, v in self.local_to_global.items() if v == gid]
            for k in keys_to_remove:
                del self.local_to_global[k]

        self.gallery.reset()
        self.id_map.clear()

        if not self.embeddings_store:
            return

        gids = list(self.embeddings_store.keys())
        embs = np.stack([self.embeddings_store[gid] for gid in gids]).astype(np.float32)

        self.gallery.add(embs)
        for i, gid in enumerate(gids):
            self.id_map[i] = gid

    def _log_match_event(
        self, global_id: str, score: float, is_new: bool, cam_id: str, track_id: int
    ) -> None:
        """
        Log a Re-ID match event for debugging.

        Args:
            global_id: The global identifier assigned or matched.
            score: The cosine similarity score (0.0 for new).
            is_new: True if a new identity was created.
            cam_id: Camera identifier.
            track_id: Local track identifier.
        """
        self.logger.debug(
            f"ReID match: cam={cam_id} track={track_id} gid={global_id} score={score:.3f} new={is_new}"
        )
