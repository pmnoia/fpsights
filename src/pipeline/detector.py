import cv2 as cv
import numpy as np


# ==========================================================
# SETTINGS
# ==========================================================

# Purple enemy outline range.
# We will tune these values using your real screenshots later.
PURPLE_LOWER = np.array([135, 120, 100], dtype=np.uint8)
PURPLE_UPPER = np.array([165, 255, 255], dtype=np.uint8)

def draw_detections(frame, result):
    output = frame.copy()

    for index, enemy in enumerate(result["enemy_positions"], start=1):
        x = enemy["x"]
        y = enemy["y"]
        width = enemy["w"]
        height = enemy["h"]

        cv.rectangle(
            output,
            (x, y),
            (x + width, y + height),
            (0, 255, 0),
            2
        )

        label = (
            f"Enemy {index} "
            f"x={x} y={y} w={width} h={height}"
        )

        cv.putText(
            output,
            label,
            (x, max(y - 10, 20)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 0),
            1,
            cv.LINE_AA
        )

    return output

def create_purple_mask(frame):
    """
    Convert the frame to HSV and keep only strong purple pixels.
    """

    hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

    mask = cv.inRange(
        hsv,
        PURPLE_LOWER,
        PURPLE_UPPER
    )

    return mask


def remove_hud_regions(mask):
    """
    Remove screen regions that commonly contain UI elements.

    These percentages work at any resolution.
    """

    height, width = mask.shape

    # Ignore top-left minimap area
    mask[
        0:int(height * 0.32),
        0:int(width * 0.25)
    ] = 0

    # Ignore top-center scoreboard area
    mask[
        0:int(height * 0.12),
        int(width * 0.30):int(width * 0.70)
    ] = 0

    # Ignore top-right kill feed
    mask[
        0:int(height * 0.30),
        int(width * 0.72):width
    ] = 0

    # Ignore bottom ability, health and weapon UI
    mask[
        int(height * 0.82):height,
        0:width
    ] = 0

    return mask


def clean_mask(mask):
    """
    Remove isolated pixels and connect nearby enemy-outline fragments.
    """

    # Remove tiny noise
    small_kernel = cv.getStructuringElement(
        cv.MORPH_ELLIPSE,
        (3, 3)
    )

    mask = cv.morphologyEx(
        mask,
        cv.MORPH_OPEN,
        small_kernel,
        iterations=1
    )

    # Connect nearby vertical outline fragments
    vertical_kernel = cv.getStructuringElement(
        cv.MORPH_RECT,
        (7, 15)
    )

    mask = cv.morphologyEx(
        mask,
        cv.MORPH_CLOSE,
        vertical_kernel,
        iterations=2
    )

    # Slightly expand the mask
    dilation_kernel = cv.getStructuringElement(
        cv.MORPH_RECT,
        (5, 9)
    )

    mask = cv.dilate(
        mask,
        dilation_kernel,
        iterations=1
    )

    return mask


def boxes_are_close(box1, box2, horizontal_gap=30, vertical_gap=40):
    """
    Check whether two boxes probably belong to the same enemy.
    """

    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    box1_left = x1
    box1_right = x1 + w1
    box1_top = y1
    box1_bottom = y1 + h1

    box2_left = x2
    box2_right = x2 + w2
    box2_top = y2
    box2_bottom = y2 + h2

    horizontally_close = (
        box1_left <= box2_right + horizontal_gap
        and box2_left <= box1_right + horizontal_gap
    )

    vertically_close = (
        box1_top <= box2_bottom + vertical_gap
        and box2_top <= box1_bottom + vertical_gap
    )

    return horizontally_close and vertically_close


def merge_two_boxes(box1, box2):
    """
    Combine two boxes into one larger box.
    """

    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    left = min(x1, x2)
    top = min(y1, y2)

    right = max(x1 + w1, x2 + w2)
    bottom = max(y1 + h1, y2 + h2)

    return (
        left,
        top,
        right - left,
        bottom - top
    )


def merge_nearby_boxes(boxes):
    """
    Merge multiple outline fragments belonging to one enemy.
    """

    boxes = boxes.copy()
    changed = True

    while changed:
        changed = False
        merged_boxes = []
        used = [False] * len(boxes)

        for i in range(len(boxes)):
            if used[i]:
                continue

            current_box = boxes[i]
            used[i] = True

            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue

                if boxes_are_close(current_box, boxes[j]):
                    current_box = merge_two_boxes(
                        current_box,
                        boxes[j]
                    )

                    used[j] = True
                    changed = True

            merged_boxes.append(current_box)

        boxes = merged_boxes

    return boxes


def find_candidate_boxes(mask):
    """
    Find boxes from the cleaned binary mask.
    """

    contours, _ = cv.findContours(
        mask,
        cv.RETR_EXTERNAL,
        cv.CHAIN_APPROX_SIMPLE
    )

    boxes = []

    for contour in contours:
        area = cv.contourArea(contour)

        # Remove tiny colored specks
        if area < 35:
            continue

        x, y, width, height = cv.boundingRect(contour)

        boxes.append((x, y, width, height))

    return boxes


def filter_enemy_boxes(boxes, frame_shape, mask):
    """
    Reject boxes that do not look like possible enemy shapes.
    """

    frame_height, frame_width = frame_shape[:2]

    enemies = []

    for x, y, width, height in boxes:
        box_area = width * height

        # Relative sizes make the detector work across resolutions
        width_ratio = width / frame_width
        height_ratio = height / frame_height

        # Too small to be useful
        if width < 6 or height < 15:
            continue

        # Usually noise or one tiny purple pixel group
        if box_area < 150:
            continue

        # Probably a large ability effect or environment object
        if width_ratio > 0.25:
            continue

        if height_ratio > 0.75:
            continue

        # Enemy boxes are generally taller than they are wide
        aspect_ratio = height / max(width, 1)

        if aspect_ratio < 1.1:
            continue

        if aspect_ratio > 6.5:
            continue

        # Reject extremely wide objects
        if width > height:
            continue

        # The color mask should occupy enough of the box
        box_mask = mask[y:y + height, x:x + width]

        colored_pixels = cv.countNonZero(box_mask)
        fill_ratio = colored_pixels / max(box_area, 1)

        if fill_ratio < 0.03:
            continue

        enemies.append({
            "x": int(x),
            "y": int(y),
            "w": int(width),
            "h": int(height),

            # This is not ML confidence.
            # It is only the percentage of colored pixels.
            "confidence": round(
                min(fill_ratio * 5, 1.0),
                3
            )
        })

    return enemies


def expand_enemy_boxes(enemies, frame_shape):
    """
    Purple pixels usually cover only the enemy outline.

    Expand boxes slightly so they better represent the full body.
    """

    frame_height, frame_width = frame_shape[:2]

    expanded = []

    for enemy in enemies:
        x = enemy["x"]
        y = enemy["y"]
        width = enemy["w"]
        height = enemy["h"]

        expand_x = int(width * 0.25)
        expand_top = int(height * 0.10)
        expand_bottom = int(height * 0.08)

        new_x = max(0, x - expand_x)
        new_y = max(0, y - expand_top)

        new_right = min(
            frame_width,
            x + width + expand_x
        )

        new_bottom = min(
            frame_height,
            y + height + expand_bottom
        )

        expanded.append({
            "x": new_x,
            "y": new_y,
            "w": new_right - new_x,
            "h": new_bottom - new_y,
            "confidence": enemy["confidence"]
        })

    return expanded


def detect(frame):
    """
    Complete purple enemy-detection pipeline.
    """

    if frame is None:
        raise ValueError("detect() received an empty frame")

    frame_height, frame_width = frame.shape[:2]

    mask = create_purple_mask(frame)
    mask = remove_hud_regions(mask)
    mask = clean_mask(mask)

    candidate_boxes = find_candidate_boxes(mask)
    merged_boxes = merge_nearby_boxes(candidate_boxes)

    enemy_positions = filter_enemy_boxes(
        merged_boxes,
        frame.shape,
        mask
    )

    enemy_positions = expand_enemy_boxes(
        enemy_positions,
        frame.shape
    )

    result = {
        "crosshair_x": frame_width // 2,
        "crosshair_y": frame_height // 2,
        "enemy_positions": enemy_positions
    }

    return result, mask