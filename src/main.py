import os
import cv2 as cv
import numpy as np

try:
    from src.utils.config import WINDOW_TITLE
except ModuleNotFoundError:
    from utils.config import WINDOW_TITLE

def detect_color(img):
    img_hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)

    # lower_red = np.array([0, 120, 70]) 
    # upper_red = np.array([10, 255, 255])

    # lower_purple = np.array([130,60,60])
    # upper_purple = np.array([155,255,255])

    # lower_purple = np.array([130,80,80])
    # upper_purple = np.array([165,255,255]) 

    lower_purple = np.array([140,110,135])
    upper_purple = np.array([155,255,255]) 

    mask = cv.inRange(img_hsv, lower_purple, upper_purple)

    result = cv.bitwise_and(img, img,mask=mask)

    cv.imshow('Valorant Screenshot', result)

    cv.waitKey(0)
    cv.destroyAllWindows

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


    # TESTING
    img = cv.imread('/Users/phonemaung/au/2026-1/csx3010/vids/ss/ss9.png')
    detect_color(img)

if __name__ == "__main__":
    main()
