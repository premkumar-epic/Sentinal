"""
SENTINAL v2 — Re-ID + Face recognition smoke tests.
Tests run without GPU, torchreid, or insightface installed.
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


class TestReIDEngine(unittest.TestCase):

    def setUp(self):
        """Import ReIDEngine — expects graceful fallback if torchreid not installed."""
        from engine.vision.reid import ReIDEngine
        # Use a dummy/nonexistent model path — ReIDEngine must not crash on import
        self.reid = ReIDEngine(model_path="models/osnet_ain_x1_0_msmt17.pth")

    def test_five_distinct_global_ids(self):
        """5 distinct embeddings → 5 distinct global_ids."""
        rng = np.random.default_rng(42)
        embeddings = [_l2_normalize(rng.standard_normal(512).astype(np.float32))
                      for _ in range(5)]
        gids = []
        for i, emb in enumerate(embeddings):
            gid = self.reid.get_or_create_global_id("cam_0", i, emb)
            gids.append(gid)
        self.assertEqual(len(set(gids)), 5, "Expected 5 distinct global_ids")

    def test_same_embeddings_return_same_global_ids(self):
        """Re-querying near-identical embeddings returns same global_ids."""
        rng = np.random.default_rng(99)
        embeddings = [_l2_normalize(rng.standard_normal(512).astype(np.float32))
                      for _ in range(5)]
        # First pass — register
        gids_first = []
        for i, emb in enumerate(embeddings):
            gid = self.reid.get_or_create_global_id("cam_1", 10 + i, emb)
            gids_first.append(gid)

        # Second pass — re-query with tiny noise
        matches = 0
        for i, emb in enumerate(embeddings):
            noisy = _l2_normalize(emb + np.random.default_rng(i).standard_normal(512).astype(np.float32) * 0.001)
            gid = self.reid.get_or_create_global_id("cam_1", 20 + i, noisy)
            if gid == gids_first[i]:
                matches += 1
        self.assertEqual(matches, 5, f"Expected 5/5 matches, got {matches}/5")

    def test_preprocess_output_shape(self):
        """_preprocess returns (256, 128, 3) uint8 array."""
        rng = np.random.default_rng(7)
        crop = (rng.integers(0, 256, size=(128, 64, 3))).astype(np.uint8)
        result = self.reid._preprocess(crop)
        self.assertEqual(result.shape, (256, 128, 3))
        self.assertEqual(result.dtype, np.uint8)


class TestFaceRecognizer(unittest.TestCase):

    def test_instantiation_no_crash(self):
        """FaceRecognizer instantiates without crashing even if insightface not installed."""
        from engine.vision.face import FaceRecognizer
        fr = FaceRecognizer()
        self.assertIsNotNone(fr)

    def test_analyze_returns_list(self):
        """analyze() returns a list (empty OK) without raising exceptions."""
        from engine.vision.face import FaceRecognizer
        fr = FaceRecognizer()
        result = fr.analyze(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertIsInstance(result, list)


if __name__ == '__main__':
    unittest.main()
