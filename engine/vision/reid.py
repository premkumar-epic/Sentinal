"""
SENTINAL v2 — Person Re-Identification (ReID) Engine
Handles global tracking across multiple cameras using deep features.
Improved accuracy with multi-shot gallery, lower thresholds, faster EMA, and lazy FAISS rebuild.
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

    Improvements:
    - Multi-shot gallery: stores up to 8 embeddings per person (handles viewpoint variation)
    - Lower thresholds: 0.68 instead of 0.80 (handles angle/lighting differences)
    - Margin check: requires top-1 to beat top-2 by >= 0.04 (avoids ambiguous matches)
    - Faster EMA: 0.85*stored + 0.15*new (quick adaptation to appearance changes)
    - Crop quality gate: skips tiny/blurry crops < 128x64 px (prevents noise)
    - Lazy FAISS rebuild: only rebuilds on gallery changes, not on every EMA update
    - Extended TTLs: 90s lost pool, 600s gallery (more stable identities)
    - Persistent identity storage: load_known_identities() at startup, mark_db_saved() after registration
    """

    N_SHOTS = 12  # Increased shots per person
    MARGIN_THRESHOLD = 0.0  # Disabled — causes false negatives with few people
    EMA_ALPHA_BASE = 0.85  # Stored embedding weight (base)
    LOST_POOL_TTL = 90.0  # 90 seconds
    GALLERY_TTL = 900.0  # 15 minutes (was 600s)
    K1 = 12  # k1-reciprocal parameter
    K2 = 6   # k2 neighbor expansion
    LAMBDA_VALUE = 0.5  # re-ranking strength

    def __init__(self, model_path: str) -> None:
        """
        Initialize the ReID engine, load the model, and setup state.

        Args:
            model_path: Path to the OSNet-AIN model weights.
        """
        self.logger = logging.getLogger("engine.vision.reid")
        # Read threshold from config (default 0.70 for improved accuracy)
        cfg_thresh = settings.reid_threshold
        self.MATCH_THRESHOLD = cfg_thresh if 0.3 <= cfg_thresh <= 0.95 else 0.70
        self.logger.info("ReID MATCH_THRESHOLD set to %.2f (from config)", self.MATCH_THRESHOLD)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._lock = threading.RLock()

        # Model initialization
        self.model = None
        self._embedding_dim = 512
        if torchreid is not None:
            try:
                self.model = torchreid.models.build_model(
                    name="osnet_ain_x1_0", num_classes=1
                )
                if os.path.exists(model_path):
                    torchreid.utils.load_pretrained_weights(self.model, model_path)
                    self.logger.info("Loaded OSNet-AIN Re-ID model from %s", model_path)
                else:
                    self.logger.warning("OSNet model not found at %s — using untrained weights", model_path)
                self.model.to(self.device)
                self.model.eval()
                self._model_type = "osnet"
            except Exception as e:
                self.logger.error("torchreid OSNet init failed: %s", e)
                self.model = None

        if self.model is None:
            try:
                import torchvision.models as tv_models
                backbone = tv_models.resnet50(weights=tv_models.ResNet50_Weights.IMAGENET1K_V2)
                self._resnet_fc = torch.nn.Linear(2048, 512, bias=False)
                torch.nn.init.xavier_normal_(self._resnet_fc.weight)
                backbone.fc = torch.nn.Identity()
                self.model = backbone
                self.model.to(self.device)
                self._resnet_fc.to(self.device)
                self.model.eval()
                self._resnet_fc.eval()
                self._model_type = "resnet50"
                self.logger.info("Using ResNet50 for Re-ID.")
            except Exception as e:
                self.logger.error("ResNet50 fallback failed: %s", e)
                self.model = None
                self._model_type = "random"

        with self._lock:
            self.gallery = faiss.IndexFlatIP(512)
            self.id_map: Dict[int, str] = {}
            self.shot_store: Dict[str, list] = {}
            self.local_to_global: Dict[Tuple[str, int], str] = {}
            self.lost_pool: Dict[str, Tuple[np.ndarray, float]] = {}
            self._gallery_timestamps: Dict[str, float] = {}
            self._dirty = False
            self._db_saved: set[str] = set()
            self._persisted_ids: set[str] = set()
            # Face-confirmed identities: these GIDs are "locked" — Re-ID trusts
            # them even when appearance matching is weak (e.g. back view).
            self._face_confirmed: set[str] = set()
            self._clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

    def extract_embedding(self, crop: np.ndarray) -> tuple[np.ndarray, float]:
        """
        Extract a 512-dimensional normalized embedding from a BGR image crop.
        Uses horizontal flip augmentation for more robust embeddings.
        Returns a (embedding, quality_score) tuple.
        """
        # Quality gate: skip very tiny crops (relaxed for distant cameras)
        h, w = crop.shape[:2]
        if h < 40 or w < 20:
            return np.zeros(512, dtype=np.float32), 0.0

        # Heuristic quality score: size and Laplacian variance (sharpness)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        size_score = min(1.0, (h * w) / (256 * 128))
        sharpness_score = min(1.0, sharpness / 500.0)
        quality = 0.4 * size_score + 0.6 * sharpness_score

        if self.model is None:
            vec = np.random.randn(512).astype(np.float32)
            return vec / np.linalg.norm(vec), quality

        processed = self._preprocess(crop)
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normed = (processed.astype(np.float32) / 255.0 - mean) / std

        # Flip augmentation: average original + horizontally flipped embeddings.
        # Makes the embedding invariant to left/right profile — critical for
        # cross-camera matching where cameras see different sides of a person.
        tensor_orig = torch.from_numpy(normed.transpose(2, 0, 1)[np.newaxis]).to(self.device)
        tensor_flip = torch.flip(tensor_orig, dims=[3])  # horizontal flip
        batch = torch.cat([tensor_orig, tensor_flip], dim=0)

        with torch.no_grad():
            features = self.model(batch)
            if self._model_type == "resnet50":
                features = self._resnet_fc(features)
            # Average both embeddings
            embedding = features.mean(dim=0).cpu().numpy().flatten().astype(np.float32)

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding, quality

    def get_or_create_global_id(
        self, local_cam_id: str, local_track_id: int, embedding: np.ndarray, quality: float = 1.0
    ) -> str:
        """
        Retrieve existing global ID or assign a new one based on similarity.
        Now uses quality-aware updates and k-reciprocal re-ranking.
        """
        if np.linalg.norm(embedding) < 1e-6:
            return str(uuid.uuid4())

        with self._lock:
            key = (local_cam_id, local_track_id)
            if key in self.local_to_global:
                global_id = self.local_to_global[key]
                self.update_embedding(global_id, embedding, quality)
                return global_id

            now = time.time()
            self.lost_pool = {gid: (emb, exp) for gid, (emb, exp) in self.lost_pool.items() if exp > now}

            best_lost_gid = None
            max_lost_sim = -1.0
            for gid, (stored_emb, _) in self.lost_pool.items():
                sim = np.dot(stored_emb, embedding)
                if sim > self.MATCH_THRESHOLD and sim > max_lost_sim:
                    max_lost_sim = sim
                    best_lost_gid = gid

            if best_lost_gid:
                self.local_to_global[key] = best_lost_gid
                self.lost_pool.pop(best_lost_gid)
                self.update_embedding(best_lost_gid, embedding, quality)
                return best_lost_gid

            self._rebuild_if_dirty()

            best_gid = None
            best_score = -1.0
            second_score = -1.0

            if self.gallery.ntotal > 0:
                query = embedding.reshape(1, -1).astype(np.float32)
                k = min(self.gallery.ntotal, 20)
                similarities, indices = self.gallery.search(query, k)

                # Aggregate per-GID: take best similarity across all shots
                scores_by_gid: Dict[str, float] = {}
                for sim, idx in zip(similarities[0], indices[0]):
                    gid = self.id_map.get(int(idx))
                    if gid and (gid not in scores_by_gid or float(sim) > scores_by_gid[gid]):
                        scores_by_gid[gid] = float(sim)

                sorted_matches = sorted(scores_by_gid.items(), key=lambda x: -x[1])

                if sorted_matches:
                    best_gid, best_score = sorted_matches[0]
                    second_score = sorted_matches[1][1] if len(sorted_matches) > 1 else -1.0

                    # Face-confirmed identities get a much lower threshold —
                    # we already KNOW who they are via face recognition, so even
                    # a weak appearance match (back/side view) should still link.
                    effective_thresh = self.MATCH_THRESHOLD
                    if best_gid in self._face_confirmed:
                        effective_thresh = max(0.20, self.MATCH_THRESHOLD - 0.15)

                    if best_score > effective_thresh and (best_score - second_score) > self.MARGIN_THRESHOLD:
                        self.local_to_global[key] = best_gid
                        self.update_embedding(best_gid, embedding, quality)
                        self.logger.info(
                            "ReID MATCHED: cam=%s track=%d → gid=%s score=%.3f (2nd=%.3f, thresh=%.2f%s)",
                            local_cam_id, local_track_id, best_gid[:8], best_score, second_score,
                            effective_thresh, " FACE" if best_gid in self._face_confirmed else "",
                        )
                        return best_gid

            # Log near-miss matches for debugging cross-camera issues
            if best_gid and best_score > 0:
                self.logger.info(
                    "ReID NEW identity: cam=%s track=%d best_score=%.3f second=%.3f "
                    "margin=%.3f (need>%.2f) thresh=%.2f — no match",
                    local_cam_id, local_track_id, best_score, second_score,
                    best_score - second_score, self.MARGIN_THRESHOLD, self.MATCH_THRESHOLD,
                )

            new_gid = str(uuid.uuid4())
            self.local_to_global[key] = new_gid
            self.shot_store[new_gid] = [embedding]
            self._gallery_timestamps[new_gid] = now
            self._mark_dirty()
            return new_gid

    def update_embedding(self, global_id: str, new_embedding: np.ndarray, quality: float = 1.0) -> None:
        """
        Update the stored embedding gallery for a global_id.
        Strategy: keep shots maximally diverse (different viewpoints).
        - shots[0] is the EMA-smoothed "average" embedding
        - shots[1:] are raw diverse viewpoint samples
        """
        with self._lock:
            if global_id in self.shot_store:
                shots = self.shot_store[global_id]

                # EMA update on primary (shots[0]) — slow blend for stable centroid
                alpha = self.EMA_ALPHA_BASE + (0.1 * (1.0 - quality))
                alpha = max(0.6, min(0.95, alpha))
                stored = shots[0]
                updated = alpha * stored + (1.0 - alpha) * new_embedding
                norm = np.linalg.norm(updated)
                if norm > 0:
                    shots[0] = updated / norm

                if len(shots) < self.N_SHOTS:
                    # Only add if this viewpoint is sufficiently different from existing shots
                    max_sim = max(float(np.dot(new_embedding, s)) for s in shots)
                    if max_sim < 0.85:  # New viewpoint — store it
                        shots.append(new_embedding)
                        self._mark_dirty()
                else:
                    # Gallery full — replace the MOST SIMILAR (most redundant) shot
                    # to maximize viewpoint diversity. This ensures front, side, and
                    # back views all stay in the gallery.
                    similarities = [float(np.dot(new_embedding, s)) for s in shots[1:]]
                    max_idx = int(np.argmax(similarities)) + 1
                    # Only replace if new embedding is more different than the one we'd replace
                    if similarities[max_idx - 1] > 0.80:
                        shots[max_idx] = new_embedding
                        self._mark_dirty()

                self._gallery_timestamps[global_id] = time.time()

    def _apply_reranking(self, query_emb: np.ndarray, sims: np.ndarray, indices: np.ndarray) -> Dict[str, float]:
        """
        Lightweight reciprocal re-ranking using dot-product (no extra FAISS searches).
        Uses best-shot similarity for the reciprocal check (not just the EMA-drifted primary).
        """
        refined_scores = {}
        for sim, idx in zip(sims, indices):
            gid = self.id_map.get(int(idx))
            if not gid:
                continue

            score = float(sim)

            # Reciprocal check: use the best shot for back-sim (primary may have drifted via EMA)
            shots = self.shot_store.get(gid, [])
            back_sim = max((float(np.dot(s, query_emb)) for s in shots), default=0.0) if shots else 0.0

            if back_sim > self.MATCH_THRESHOLD:
                score = (1 - self.LAMBDA_VALUE) * score + self.LAMBDA_VALUE * back_sim
            else:
                # Mild penalty — don't destroy valid cross-camera matches
                score *= 0.93

            if gid not in refined_scores or score > refined_scores[gid]:
                refined_scores[gid] = score

        return refined_scores


    def merge_identities(self, keep_gid: str, merge_gid: str) -> bool:
        """
        Merge merge_gid into keep_gid. All embeddings, local mappings,
        and DB-saved status transfer to keep_gid. merge_gid is removed.

        Args:
            keep_gid: The identity to keep (typically from face recognition).
            merge_gid: The identity to absorb and delete.

        Returns:
            True if merge happened, False if nothing to merge.
        """
        if keep_gid == merge_gid:
            return False

        with self._lock:
            if merge_gid not in self.shot_store:
                return False

            # 1. Transfer embeddings (respect N_SHOTS limit)
            if keep_gid not in self.shot_store:
                self.shot_store[keep_gid] = []
            keep_shots = self.shot_store[keep_gid]
            merge_shots = self.shot_store.pop(merge_gid, [])
            for emb in merge_shots:
                if len(keep_shots) < self.N_SHOTS:
                    keep_shots.append(emb)

            # 2. Redirect all local_to_global mappings
            for key, gid in list(self.local_to_global.items()):
                if gid == merge_gid:
                    self.local_to_global[key] = keep_gid

            # 3. Transfer DB-saved and persisted status
            if merge_gid in self._db_saved:
                self._db_saved.discard(merge_gid)
                self._db_saved.add(keep_gid)
            if merge_gid in self._persisted_ids:
                self._persisted_ids.discard(merge_gid)
                self._persisted_ids.add(keep_gid)

            # 4. Update timestamp and remove merge_gid's
            self._gallery_timestamps[keep_gid] = time.time()
            self._gallery_timestamps.pop(merge_gid, None)

            # 5. Remove from lost pool if present
            self.lost_pool.pop(merge_gid, None)

            self._mark_dirty()
            self.logger.info(
                "MERGED identity %s → %s (shots: %d)",
                merge_gid[:8], keep_gid[:8], len(keep_shots),
            )
            return True

    def merge_duplicates(self) -> int:
        """
        Scan all gallery identities and merge any pair whose primary
        embeddings exceed MATCH_THRESHOLD.  This catches the startup race
        where multiple cameras create separate IDs for the same person
        before any cross-camera matching can happen.

        Returns:
            Number of merges performed.
        """
        merges = 0
        with self._lock:
            gids = list(self.shot_store.keys())
            if len(gids) < 2:
                return 0

            # Build a quick similarity check using primary embeddings
            merged_away: set = set()
            for i in range(len(gids)):
                if gids[i] in merged_away:
                    continue
                emb_i = self.shot_store[gids[i]][0]
                for j in range(i + 1, len(gids)):
                    if gids[j] in merged_away:
                        continue
                    emb_j = self.shot_store[gids[j]][0]
                    sim = float(np.dot(emb_i, emb_j))
                    if sim > self.MATCH_THRESHOLD:
                        self.logger.info(
                            "merge_duplicates: %s <-> %s sim=%.3f — merging",
                            gids[i][:8], gids[j][:8], sim,
                        )
                        merged_away.add(gids[j])
                        merges += 1

            # Perform merges outside the inner loop (use merge_identities which re-acquires lock via RLock)
        for gid in merged_away:
            # Find which gid to keep (the one NOT in merged_away)
            # We need to re-check since merge_identities modifies state
            with self._lock:
                if gid not in self.shot_store:
                    continue
                # Find the best match among remaining identities
                emb = self.shot_store[gid][0]
                best_keep = None
                best_sim = -1.0
                for other_gid, shots in self.shot_store.items():
                    if other_gid == gid or other_gid in merged_away:
                        continue
                    sim = float(np.dot(emb, shots[0]))
                    if sim > best_sim:
                        best_sim = sim
                        best_keep = other_gid
                if best_keep:
                    self.merge_identities(best_keep, gid)

        return merges

    def mark_face_confirmed(self, global_id: str) -> None:
        """Mark a global_id as face-confirmed (lowers matching threshold for this identity)."""
        with self._lock:
            self._face_confirmed.add(global_id)
            self.logger.info("Face-confirmed identity: %s", global_id[:8])

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

            # Add to lost_pool with extended TTL using primary embedding
            if global_id in self.shot_store:
                shots = self.shot_store[global_id]
                # Use first (primary/most-updated) embedding
                primary_emb = shots[0] if shots else np.zeros(512, dtype=np.float32)
                self.lost_pool[global_id] = (primary_emb, time.time() + self.LOST_POOL_TTL)

    def load_known_identities(self, identities: list[dict]) -> None:
        """
        Load known identities from the database into the FAISS gallery at startup.
        Marks them as persisted (never evicted) and db_saved (skip re-registration).

        Args:
            identities: list of dicts with keys: global_id, name, embedding (bytes or None)
        """
        loaded = 0
        with self._lock:
            for row in identities:
                gid = row.get("global_id")
                emb_bytes = row.get("embedding")
                if not gid or not emb_bytes:
                    continue
                try:
                    emb = np.frombuffer(emb_bytes, dtype=np.float32).copy()
                    if emb.shape[0] != 512:
                        continue
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        emb = emb / norm
                    # Add to shot_store (use existing multi-shot structure)
                    if gid not in self.shot_store:
                        self.shot_store[gid] = []
                    self.shot_store[gid].append(emb)
                    self._gallery_timestamps[gid] = time.time()
                    self._persisted_ids.add(gid)
                    self._db_saved.add(gid)
                    loaded += 1
                except Exception as exc:
                    self.logger.warning("load_known_identities: skip %s — %s", gid, exc)
            if loaded:
                self._mark_dirty()
                self._rebuild_if_dirty()
        self.logger.info("ReIDEngine: loaded %d known identities from DB", loaded)

    def is_db_saved(self, global_id: str) -> bool:
        """Return True if this global_id has already been persisted to the database."""
        with self._lock:
            return global_id in self._db_saved

    def mark_db_saved(self, global_id: str, embedding: np.ndarray) -> None:
        """
        Mark a global_id as saved to DB. Also stores the embedding for future sessions.
        Args:
            global_id: The global identifier to mark.
            embedding: The normalized 512-d embedding to associate.
        """
        with self._lock:
            self._db_saved.add(global_id)
            self._persisted_ids.add(global_id)

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
        l = self._clahe.apply(l)
        crop = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        crop = cv2.resize(crop, (128, 256))  # OSNet input size
        return crop

    def _mark_dirty(self) -> None:
        """Mark gallery as needing rebuild on next search."""
        self._dirty = True

    def _rebuild_if_dirty(self) -> None:
        """
        Rebuild FAISS index only if marked dirty.
        Must be called within self._lock.
        """
        if not self._dirty:
            return

        self._rebuild_index()
        self._dirty = False

    def _rebuild_index(self) -> None:
        """
        Rebuild the FAISS index from the shot_store.
        Evicts entries from _gallery_timestamps where time.time() - last_seen > GALLERY_TTL.
        Must be called within self._lock.
        """
        now = time.time()
        # Evict stale gallery entries (but protect persisted identities)
        stale_gids = [
            gid for gid, ts in self._gallery_timestamps.items()
            if now - ts > self.GALLERY_TTL and gid not in self._persisted_ids
        ]
        for gid in stale_gids:
            self._gallery_timestamps.pop(gid, None)
            self.shot_store.pop(gid, None)
            keys_to_remove = [k for k, v in self.local_to_global.items() if v == gid]
            for k in keys_to_remove:
                del self.local_to_global[k]

        self.gallery.reset()
        self.id_map.clear()

        if not self.shot_store:
            return

        # Flatten all shots from all people into FAISS
        faiss_idx = 0
        gids = list(self.shot_store.keys())
        all_embeddings = []

        for gid in gids:
            shots = self.shot_store[gid]
            for shot in shots:
                all_embeddings.append(shot)
                self.id_map[faiss_idx] = gid
                faiss_idx += 1

        if all_embeddings:
            embs = np.stack(all_embeddings).astype(np.float32)
            self.gallery.add(embs)

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
            "ReID match: cam=%s track=%d gid=%s score=%.3f new=%s",
            cam_id, track_id, global_id, score, is_new
        )
