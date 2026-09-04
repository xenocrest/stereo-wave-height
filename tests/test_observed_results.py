"""Small read-only demo review contract and widget regressions."""
import hashlib
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from PIL import Image
from application.observed_results import load_review, ObservedResultsPanel


class ObservedReviewTests(unittest.TestCase):
    def fixture(self, root):
        path = root / "frame.jpg"
        Image.new("RGB", (96, 54), "green").save(path)
        frame = dict(frame_id="000000", left_target_s=1, decoded_pts_s=[1, .775],
                     final_xyz_count=40, raw_roi_support_ratio=.0075, stereo_seconds=12)
        for key in ("original", "support"):
            frame[key] = path.name
            frame[key+"_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        result = root / "review.json"
        result.write_text(json.dumps(dict(schema="wass_observation_review_v1", height_available=False,
            experiment="fixture", fixed_roi_pixels=10000, fixed_roi_full_image_ratio=.33,
            frames=[frame, dict(frame, frame_id="000001", raw_roi_support_ratio=0)])), encoding="utf-8")
        return result

    def test_review_preserves_zero_support_and_rejects_modified_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = self.fixture(root)
            self.assertEqual(load_review(path)["frames"][1]["raw_roi_support_ratio"], 0)
            (root / "frame.jpg").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"): load_review(path)

    def test_cannot_present_heights_as_observation_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory)); data=json.loads(path.read_text())
            data["height_available"] = True; path.write_text(json.dumps(data))
            with self.assertRaises(ValueError): load_review(path)

    def test_actual_widget_switches_frames_without_modifying_bundle(self):
        try: window = tk.Tk()
        except tk.TclError as error: self.skipTest(str(error))
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = self.fixture(Path(directory)); before=path.read_bytes()
                panel=ObservedResultsPanel(window, path); panel.pack(); window.update()
                panel.show_frame(1); window.update()
                self.assertIn("0.0000%", panel.summary.get())
                panel.mode.set("original"); panel.show_frame(0); window.update()
                self.assertIsNotNone(panel.photo)
                self.assertEqual(before, path.read_bytes())
        finally: window.destroy()
