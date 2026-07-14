import cv2 as cv

from detector import detect, draw_detections


IMAGE_PATH = "../../screenshots/test14.jpg"


def main():
    frame = cv.imread(IMAGE_PATH)

    if frame is None:
        raise FileNotFoundError(
            f"Could not load image: {IMAGE_PATH}"
        )

    result, mask = detect(frame)
    output = draw_detections(frame, result)

    print("=" * 60)
    print("Enemies found:", len(result["enemy_positions"]))

    for enemy in result["enemy_positions"]:
        print(enemy)

    print("=" * 60)

    cv.imshow("Original", frame)
    cv.imshow("Purple mask", mask)
    cv.imshow("Final detections", output)

    cv.imwrite(
        "../../output/debug_mask.png",
        mask
    )

    cv.imwrite(
        "../../output/debug_detection.png",
        output
    )

    cv.waitKey(0)
    cv.destroyAllWindows()


if __name__ == "__main__":
    main()