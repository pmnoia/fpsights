"""YOLO-based enemy detection."""

from pathlib import Path
from typing import Any

import cv2 as cv


class YoloDetector:
    """Load trained YOLO weights and return JSON-friendly detections."""

    def __init__(
        self,
        model_path: str | Path,
        confidence: float = 0.25,
        device: str | None = None,
    ) -> None:
        model_file = Path(model_path)

        if not model_file.is_file():
            raise FileNotFoundError(f"Could not find YOLO weights: {model_file}")

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError(
                "Ultralytics is not installed. Run: pip install -r requirements.txt"
            ) from error

        self.model = YOLO(str(model_file))
        self.confidence = confidence
        self.device = device

    def detect(self, frame: Any) -> dict[str, Any]:
        if frame is None:
            raise ValueError("detect() received an empty frame")

        prediction = self.model.predict(
            source=frame,
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )[0]

        enemy_positions = []

        if prediction.boxes is not None:
            for box in prediction.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                class_id = int(box.cls[0].item())
                x = int(round(x1))
                y = int(round(y1))
                right = int(round(x2))
                bottom = int(round(y2))

                enemy_positions.append(
                    {
                        "x": x,
                        "y": y,
                        "w": max(0, right - x),
                        "h": max(0, bottom - y),
                        "confidence": round(float(box.conf[0].item()), 4),
                        "class_id": class_id,
                        "class_name": _class_name(prediction.names, class_id),
                    }
                )

        height, width = frame.shape[:2]

        return {
            "crosshair_x": width // 2,
            "crosshair_y": height // 2,
            "enemy_positions": enemy_positions,
        }


def _class_name(names: Any, class_id: int) -> str:
    if isinstance(names, dict):
        return str(names.get(class_id, class_id))

    if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
        return str(names[class_id])

    return str(class_id)


def draw_detections(frame: Any, result: dict[str, Any]) -> Any:
    """Draw YOLO detections on a copy of a frame for optional preview."""
    output = frame.copy()

    for enemy in result["enemy_positions"]:
        x, y = enemy["x"], enemy["y"]
        width, height = enemy["w"], enemy["h"]
        label = f'{enemy["class_name"]} {enemy["confidence"]:.2f}'

        cv.rectangle(output, (x, y), (x + width, y + height), (0, 255, 0), 2)
        cv.putText(
            output,
            label,
            (x, max(y - 8, 20)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv.LINE_AA,
        )

    return output
