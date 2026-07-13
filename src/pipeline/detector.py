import cv2 as cv
import numpy as np
import os

HIGHLIGHT_COLORS = {
    "red": [
        (np.array([0, 120, 100]), np.array([10, 255, 255])),
        (np.array([170, 120, 100]), np.array([180, 255, 255]))
    ],

    "yellow": [
        (np.array([20, 120, 120]), np.array([40, 255, 255]))
    ],

    "purple": [
        (np.array([130, 80, 80]), np.array([165, 255, 255])) # lo hi 1: [130,60,60] [155,255,255] lo hi 2: [140, 110, 135] [155, 255, 255]
    ]
}

def detect(frame, frame_number=0, timestamp_ms=0.0, prev_frame=None, method="color", highlight_color="purple"):
    # Run detection on one frame and return a dict
    # method="motion" needs prev_frame; method="color" uses highlight_color
    height, width = frame.shape[:2]
    crosshair_x, crosshair_y = get_crosshair(width, height)

    if method == "motion":
        enemy_pos = motion(frame, prev_frame) if prev_frame is not None else []
    elif method == "color":
        enemy_pos = color(frame, highlight_color)
    else:
        raise ValueError(f"method must be 'motion' or 'color', got '{method}'")

    return {
        "frame_number":    frame_number,
        "timestamp_ms":    timestamp_ms,
        "crosshair_x":     crosshair_x,
        "crosshair_y":     crosshair_y,
        "enemy_positions": enemy_pos,
        "detector_meta":   {"method": method, "crosshair_confidence": 1.0},
    }

def motion(frame, prev_frame, min_area=2_000, max_area=80_000):
#     # Frame-diff: find anything that moves between two frames
#     curr = cv.GaussianBlur(cv.cvtColor(frame, cv.COLOR_BGR2GRAY), (7, 7), 0)
#     prev = cv.GaussianBlur(cv.cvtColor(prev_frame, cv.COLOR_BGR2GRAY), (7, 7), 0)

#     diff = cv.absdiff(curr, prev)
#     _, threshold = cv.threshold(diff, 25, 255, cv.THRESH_BINARY)
#     threshold = cv.dilate(threshold, np.ones((7,7), np.uint8), iterations=2)

#     contours, _ = cv.findContours(threshold, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
#     return boxes(contours, min_area, max_area, min_aspect=1.0)
    return []

def color(frame, highlight_color, min_box_area=800, max_box_area=60_000):
    hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

    mask = np.zeros(frame.shape[:2], dtype=np.uint8)

    for lo, hi in HIGHLIGHT_COLORS[highlight_color]:
        current_mask = cv.inRange(hsv, lo, hi)
        mask = cv.bitwise_or(mask, current_mask)

    height, width = mask.shape

    # Remove HUD areas
    mask[:int(height * 0.13), :] = 0                  # top HUD
    mask[int(height * 0.88):, :] = 0                  # bottom HUD
    mask[:int(height * 0.38), :int(width * 0.25)] = 0 # minimap
    mask[:int(height * 0.25), int(width * 0.68):] = 0 # kill feed

    # Remove player weapon area, mostly bottom-right
    mask[int(height * 0.65):, int(width * 0.45):] = 0

    # Connect nearby enemy outline pieces
    close_kernel = np.ones((9, 9), np.uint8)
    mask = cv.morphologyEx(mask, cv.MORPH_CLOSE, close_kernel)

    # Make thin outline thicker
    dilate_kernel = np.ones((3, 3), np.uint8)
    mask = cv.dilate(mask, dilate_kernel, iterations=1)

    # Debug mask
    cv.imwrite("debug_mask.png", mask)

    contours, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    enemy_boxes = color_boxes(contours, mask, min_box_area, max_box_area)

    # Keep best candidates only
    #enemy_boxes = sorted(enemy_boxes, key=lambda b: b["confidence"], reverse=True)

    return enemy_boxes[:5]

def color_boxes(contours, mask, min_box_area, max_box_area):
    enemy_boxes = []

    for c in contours:
        x, y, w, h = cv.boundingRect(c)

        box_area = w * h

        # Ignore tiny boxes and huge wrong boxes
        if box_area < min_box_area or box_area > max_box_area:
            continue

        # Enemy should not be too tiny
        if w < 8 or h < 20:
            continue

        aspect_ratio = h / max(w, 1)

        # Human shape is usually taller than wide
        if aspect_ratio < 1.0 or aspect_ratio > 7.0:
            continue

        colored_pixels = cv.countNonZero(mask[y:y+h, x:x+w])
        fill_ratio = colored_pixels / box_area

        # Ignore weak small color pieces
        if colored_pixels < 100:
            continue

        if fill_ratio < 0.05:
            continue

        confidence = min(1.0, fill_ratio * 2.5)

        enemy_boxes.append({
            "x": int(x),
            "y": int(y),
            "w": int(w),
            "h": int(h),
            "confidence": round(float(confidence), 3)
        })

    return enemy_boxes

# def boxes(contours, min_area, max_area, min_aspect):
#     boxes = []
#     for c in contours:
#         area = cv.contourArea(c)
#         if not (min_area <= area <= max_area):
#             continue
#         x,y,w,h = cv.boundingRect(c)
#         if h / max(w, 1) < min_aspect:
#             continue
#         conf = min(area / 40_000, 1.0)
#         boxes.append({"x": x, "y": y, "w": w, "h": h, "confidence": round(conf, 3)})
#     return boxes

def get_crosshair(width, height):
    return width // 2, height // 2

def save_debug_frame(frame, result, debug_dir, processed_index, limit=200):
    """Save annotated preview image. Only runs for the first `limit` frames."""
    if processed_index >= limit:
        return
    os.makedirs(debug_dir, exist_ok=True)
    vis = frame.copy()

    cv.drawMarker(vis, (result["crosshair_x"], result["crosshair_y"]),
                  (0, 255, 0), cv.MARKER_CROSS, markerSize=20, thickness=2)

    for b in result["enemy_positions"]:
        cv.rectangle(vis, (b["x"], b["y"]), (b["x"]+b["w"], b["y"]+b["h"]), (0, 0, 255), 2)
        cv.putText(vis, f"{b['confidence']:.2f}", (b["x"], b["y"]-6),
                   cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    cv.putText(vis,
               f"frame={result['frame_number']}  t={result['timestamp_ms']:.0f}ms  "
               f"enemies={len(result['enemy_positions'])}",
               (10, 24), cv.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1)

    cv.imwrite(os.path.join(debug_dir, f"debug_{result['frame_number']:06d}.jpg"), vis)

# def detect_enemies(frame):
#     # use HSV instead of RGB
#     hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

#     lower_red1 = np.array([0, 200, 150])
#     upper_red1 = np.array([10, 255, 255])
#     lower_red2 = np.array([170, 200, 150])
#     upper_red2 = np.array([180, 255, 255])

#     mask = cv.add(
#         cv.inRange(hsv, lower_red1, upper_red1),
#         cv.inRange(hsv, lower_red2, upper_red2),
#     )

#     # Find contours in mask
#     contours, hierarchy = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

#     enemies = []
#     for contour in contours:
#         area = cv.contourArea(contour)
#         if area < 3000: # min area
#             continue # too small - probably noise
        
#         x, y, w, h = cv.boundingRect(contour)
#         enemies.append({
#             "x": x,
#             "y": y,
#             "w": w,
#             "h": h,
#             "confidence": 0.5, # replace this hard coded value
#         })
#     return enemies
