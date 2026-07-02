import os
from pipeline.detector import detect

try:
    from src.utils.config import WINDOW_TITLE
except ModuleNotFoundError:
    from utils.config import WINDOW_TITLE


import cv2 as cv

def main() -> None:
    print(f"{WINDOW_TITLE} setup is ready.")

    # img = cv.imread('/Users/phonemaung/Downloads/sae-3.jpg')

    # cv.imshow('Sage', img)

    # # Convert to grayscale
    # gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    # cv.imshow('Gray', gray)

    # # Blur
    # blur = cv.GaussianBlur(img, (7,7), cv.BORDER_DEFAULT)
    # cv.imshow('Blur', blur)

    # # Edge Cascade
    # canny = cv.Canny(blur, 125, 175)
    # cv.imshow('Canny Edges', canny)

    # # Dilating the image
    # dilated = cv.dilate(canny, (7,7), iterations=3)
    # cv.imshow('Dilated', dilated)

    # # Eroding 
    # eroded = cv.erode(dilated, (7,7), iterations=3)
    # cv.imshow('Eroded', eroded)

    # # Resize
    # resized = cv.resize(img, (500,500), interpolation=cv.INTER_CUBIC)
    # cv.imshow('Resized', resized)

    # # Crop
    # cropped = img[50:200, 200:400]
    # cv.imshow('Cropped', cropped)
    
    # cv.waitKey(0)


    # TESTING detector
    frame = cv.imread('/Users/phonemaung/au/2026-1/csx3010/vids/ss/ss1.png')
    test_result = detect(frame)
    print(test_result["crosshair_x"], test_result["crosshair_y"])
    print(test_result["enemy_positions"])  # [] if nothing red found     

if __name__ == "__main__":
    main()
