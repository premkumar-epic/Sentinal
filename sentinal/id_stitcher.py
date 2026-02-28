from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torchvision.models as models
import torchvision.transforms as T


BBox = Tuple[float, float, float, float]


@dataclass(frozen=True)
class StitcherConfig:
    enabled: bool = True
    ttl_seconds: float = 8.0
    min_similarity: float = 0.75  # Cosine similarity threshold
    max_lost: int = 50


@dataclass
class _LostTrack:
    stable_id: int
    features: np.ndarray
    last_seen: float


class TrackIdStitcher:
    """Best-effort ID persistence across short exits/entries.

    Stitches IDs using deep feature embeddings (MobileNetV3) over a short time window
    to robustly re-identify recurrent persons.
    """

    def __init__(self, config: StitcherConfig) -> None:
        self._cfg = config
        self._next_stable_id = 1
        self._active_map: Dict[int, int] = {}  # track_id -> stable_id
        self._lost: List[_LostTrack] = []
        
        if config.enabled:
            # Initialize MobileNetV3 for feature extraction
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self._model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
            self._model.classifier = torch.nn.Identity()  # Remove classifier to get pure embeddings
            self._model.to(self._device)
            self._model.eval()
            
            self._transform = T.Compose([
                T.ToPILImage(),
                T.Resize((224, 224)),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])

    def assign(self, frame: np.ndarray, tracks: Iterable[dict]) -> List[dict]:
        """Return tracks with an added 'stable_id' field."""
        tracks_list = [t for t in tracks if "track_id" in t and "bbox" in t]
        if not self._cfg.enabled or not tracks_list:
            for t in tracks_list:
                tid = int(t["track_id"])
                t["stable_id"] = tid
            return tracks_list

        now = monotonic()
        self._purge_expired(now)

        current_track_ids = {int(t["track_id"]) for t in tracks_list}

        # Move disappeared track IDs into lost pool.
        disappeared = [tid for tid in list(self._active_map.keys()) if tid not in current_track_ids]
        for tid in disappeared:
            stable_id = self._active_map.pop(tid)
            self._mark_lost(stable_id, now)

        # Precompute features in a single batch to avoid extreme delay
        track_features = self._compute_batch_features(frame, tracks_list)

        # Assign stable IDs to current tracks.
        used_stable_ids = set(self._active_map.values())
        for idx, t in enumerate(tracks_list):
            tid = int(t["track_id"])
            if tid in self._active_map:
                t["stable_id"] = self._active_map[tid]
                continue

            features = track_features[idx]
            if features is None:
                stable_id = self._new_stable_id(used_stable_ids, preferred=tid)
                self._active_map[tid] = stable_id
                used_stable_ids.add(stable_id)
                t["stable_id"] = stable_id
                t["reid_score"] = 1.0
                continue

            match_id, match_score = self._best_match(features, used_stable_ids)
            if match_id is not None:
                stable_id = match_id
                t["reid_score"] = match_score
            else:
                stable_id = self._new_stable_id(used_stable_ids, preferred=tid)
                t["reid_score"] = 1.0
            self._active_map[tid] = stable_id
            used_stable_ids.add(stable_id)
            t["stable_id"] = stable_id

        # Update features for all active tracks and keep a fresh lost copy to stitch from.
        for idx, t in enumerate(tracks_list):
            stable_id = int(t["stable_id"])
            features = track_features[idx]
            if features is not None:
                self._upsert_lost(stable_id, features, now)

        return tracks_list

    def _new_stable_id(self, used: set[int], preferred: Optional[int] = None) -> int:
        if preferred is not None and preferred not in used:
            return int(preferred)
        while self._next_stable_id in used:
            self._next_stable_id += 1
        sid = self._next_stable_id
        self._next_stable_id += 1
        return sid

    def _purge_expired(self, now: float) -> None:
        ttl = self._cfg.ttl_seconds
        self._lost = [lt for lt in self._lost if now - lt.last_seen <= ttl]
        if len(self._lost) > self._cfg.max_lost:
            # Keep most recent
            self._lost.sort(key=lambda x: x.last_seen, reverse=True)
            self._lost = self._lost[: self._cfg.max_lost]

    def _best_match(self, features: np.ndarray, used_stable_ids: set[int]) -> Tuple[Optional[int], float]:
        best_id: Optional[int] = None
        best_score = -1.0
        for lt in self._lost:
            if lt.stable_id in used_stable_ids:
                continue
            # Cosine similarity
            score = float(np.dot(lt.features, features) / (np.linalg.norm(lt.features) * np.linalg.norm(features) + 1e-7))
            if score > best_score:
                best_score = score
                best_id = lt.stable_id
        import logging
        logging.getLogger("sentinal.reid").debug("Best match candidate: id=%s score=%.4f threshold=%.2f", best_id, best_score, self._cfg.min_similarity)
        if best_id is not None and best_score >= self._cfg.min_similarity:
            return best_id, best_score
        return None, 0.0

    def _compute_batch_features(self, frame: np.ndarray, tracks: List[dict]) -> List[Optional[np.ndarray]]:
        h, w = frame.shape[:2]
        tensors = []
        valid_indices = []
        
        for i, t in enumerate(tracks):
            x1, y1, x2, y2 = t["bbox"]
            ix1 = max(0, min(w - 1, int(x1)))
            iy1 = max(0, min(h - 1, int(y1)))
            ix2 = max(0, min(w, int(x2)))
            iy2 = max(0, min(h, int(y2)))
            
            if ix2 <= ix1 or iy2 <= iy1:
                continue
            
            crop = frame[iy1:iy2, ix1:ix2]
            if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
                continue
                
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            try:
                tensor = self._transform(crop_rgb)
                tensors.append(tensor)
                valid_indices.append(i)
            except Exception:
                continue
                
        results: List[Optional[np.ndarray]] = [None] * len(tracks)
        if not tensors:
            return results
            
        try:
            batch = torch.stack(tensors).to(self._device)
            with torch.inference_mode():
                feats = self._model(batch).cpu().numpy()
            
            for list_idx, feat in zip(valid_indices, feats):
                results[list_idx] = feat.flatten()
        except Exception:
            pass
            
        return results

    def _upsert_lost(self, stable_id: int, features: np.ndarray, now: float) -> None:
        for lt in self._lost:
            if lt.stable_id == stable_id:
                lt.features = features
                lt.last_seen = now
                return
        self._lost.append(_LostTrack(stable_id=stable_id, features=features, last_seen=now))

    def _mark_lost(self, stable_id: int, now: float) -> None:
        for lt in self._lost:
            if lt.stable_id == stable_id:
                lt.last_seen = now
                return
