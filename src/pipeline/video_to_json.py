import argparse

from frame_reader import read_frames
from detector import detect
from json_writer import save_json
from detector import detect, draw_detections


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect enemies in Valorant gameplay video."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input video"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to the output JSON file"
    )

    parser.add_argument(
        "--frame-skip",
        type=int,
        default=5,
        help="Process every Nth frame"
    )

    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum number of processed frames"
    )

    parser.add_argument(
        "--color",
        choices=["purple", "yellow", "red"],
        default="purple",
        help="Enemy highlight color"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    results = []

    for frame_number, frame in read_frames(
        video_path=args.input,
        frame_skip=args.frame_skip,
        max_frames=args.max_frames
    ):
        import cv2 as cv
        
        detection = detect(
            frame,
            highlight_color=args.color
        )
        
        debug_frame = draw_detections(frame, detection)

        cv.imshow("FPSights Detection", debug_frame)

        if cv.waitKey(1) & 0xFF == ord("q"):
            break

        frame_result = {
            "frame_number": frame_number,
            **detection
        }

        results.append(frame_result)

        enemy_count = len(
            detection["enemy_positions"]
        )

        print(
            f"Frame {frame_number}: "
            f"{enemy_count} possible enemies"
        )

    output_data = {
        "video": args.input,
        "highlight_color": args.color,
        "processed_frames": len(results),
        "frames": results
    }

    save_json(output_data, args.output)

    print(f"Results saved to: {args.output}")

    cv.destroyAllWindows()


if __name__ == "__main__":
    main()