import argparse
import cv2 as cv

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract frames from a video and save metadata to JSON."
    )

    # Path to the input file
    parser.add_argument(
        "--input",
        required=True,
        help="Path to video file (e.g. valorant.mp4)"
    )

    # Path where output will be
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output JSON file"
    )

    # Process every N frame
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=3,
        help="Process every Nth frame. Default is 3."
    )

    # Total number of frames processed
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum number of frames to process."
    )

    return parser.parse_args()

def main():
    args = parse_args()
    print("Input video: ", args.input)
    print("Output JSON", args.output) 
    print("Frame skip: ", args.frame_skip)
    print("Max frames: ", args.max_frames)

# Reading Videos
def process_video(input_path):
    capture = cv.VideoCapture(input_path)

    if not capture.isOpened():
        print("Whoops!!! Could not open video.")
        return

    while True:
        isTrue, frame = capture.read()

        if not isTrue or frame is None:
            break

        frame_resized = rescale_frame(frame)

        cv.imshow('Valorant', frame)
        cv.imshow('Valorant Resized', frame_resized)

        if cv.waitKey(20) & 0xFF==ord('d'): # if letter d is pressed break out loop
            break

    capture.release()
    cv.destroyAllWindows()

# Resizes to particular dimensions
def rescale_frame(frame, scale=0.75):
    # img, vids, and live vids OK
    width = int(frame.shape[1] * scale)
    height = int(frame.shape[0] * scale)
    
    dimensions = (width, height)

    return cv.resize(frame, dimensions, interpolation=cv.INTER_AREA)


if __name__ == "__main__":
    #main()
    args = parse_args()
    #vid_path = input("Enter vid path: ")
    process_video(args.input)

    print(f"Input video: {args.input}")
    print(f"Output JSON : {args.output}")
    print(f"Frame skip : {args.frame_skip}")
    print(f"Max frames : {args.max_frames}")