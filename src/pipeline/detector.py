import cv2 as cv
import numpy as np

def detect(frame):
    height, width = frame.shape[:2]
    crosshair_x, crosshair_y = get_crosshair(width, height)
    enemy_pos = detect_enemies(frame)

    frame_info = {
        "crosshair_x": crosshair_x,
        "crosshair_y": crosshair_y,
        "enemy_positions": enemy_pos
    }
    return frame_info

def get_crosshair(width, height):
    return width // 2, height // 2

def detect_enemies(frame):
    # use HSV instead of RGB
    hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 120, 70])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 120, 70])
    upper_red2 = np.array([180, 255, 255])

    mask = cv.add(
        cv.inRange(hsv, lower_red1, upper_red1),
        cv.inRange(hsv, lower_red2, upper_red2),
    )

    # Find contours in mask
    contours, hierarchy = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    enemies = []
    for contour in contours:
        area = cv.contourArea(contour)
        if area < 800: # min area
            continue # too small - probably noise
        
        x, y, w, h = cv.boundingRect(contour)
        enemies.append({
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "confidence": 0.5, # replace this hard coded value
        })
    
    return enemies