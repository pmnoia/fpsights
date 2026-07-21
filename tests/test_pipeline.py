"""Tests for the small YOLO inference boundary."""

import unittest
from types import SimpleNamespace

from src.pipeline.detector import YoloDetector
from src.pipeline.frame_reader import read_frames


class _TensorValue:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _Coordinates:
    def tolist(self):
        return [10.2, 20.4, 40.7, 80.9]


class _FakeModel:
    def predict(self, **_kwargs):
        box = SimpleNamespace(
            xyxy=[_Coordinates()],
            cls=[_TensorValue(0)],
            conf=[_TensorValue(0.87654)],
        )
        prediction = SimpleNamespace(boxes=[box], names={0: "enemy"})
        return [prediction]


class YoloDetectorTests(unittest.TestCase):
    def test_detect_serializes_prediction(self):
        detector = YoloDetector.__new__(YoloDetector)
        detector.model = _FakeModel()
        detector.confidence = 0.25
        detector.device = "cpu"
        frame = SimpleNamespace(shape=(1080, 1920, 3))

        result = detector.detect(frame)

        self.assertEqual(result["crosshair_x"], 960)
        self.assertEqual(result["crosshair_y"], 540)
        self.assertEqual(
            result["enemy_positions"],
            [
                {
                    "x": 10,
                    "y": 20,
                    "w": 31,
                    "h": 61,
                    "confidence": 0.8765,
                    "class_id": 0,
                    "class_name": "enemy",
                }
            ],
        )

    def test_missing_weights_fail_before_model_load(self):
        with self.assertRaises(FileNotFoundError):
            YoloDetector("missing.pt")


class FrameReaderTests(unittest.TestCase):
    def test_frame_skip_must_be_positive(self):
        with self.assertRaises(ValueError):
            next(read_frames("unused.mp4", frame_skip=0))

    def test_max_frames_must_be_positive(self):
        with self.assertRaises(ValueError):
            next(read_frames("unused.mp4", max_frames=0))


if __name__ == "__main__":
    unittest.main()
