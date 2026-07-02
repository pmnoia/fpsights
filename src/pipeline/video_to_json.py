import argparse
import cv2 as cv
import json
import os
import sys
from detector import detect

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

# Reading Videos
def process_video(input_path, output_json, frame_skip, max_frames):
    # Open the video
    capture = cv.VideoCapture(input_path)

    if not capture.isOpened():
        print(f"Whoops!!! Could not open video: {input_path}")
        sys.exit(1)

    # Read video properties
    fps = capture.get(cv.CAP_PROP_FPS)
    width = int(capture.get(cv.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(capture.get(cv.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps

    print(f"Video       : {input_path}")
    print(f"Resolution  : {width}x{height}")
    print(f"FPS         : {fps}")
    print(f"Duration    : {duration_sec}s ({total_frames} total frames)")
    print(f"Frame skip  : every {frame_skip} frame(s)")
    print()

    # Create a folder to save the extracted frame images 
    # This turns output.json → output_frames/ automatically.
    frames_dir = os.path.splitext(output_json)[0] + "_frames" 
    os.makedirs(frames_dir, exist_ok=True)

    frames_data = []
    frame_index = 0
    saved_count = 0

    while True:
        isTrue, frame = capture.read()

        if not isTrue or frame is None:
            break # end of video

        # Keep only every Nth frame
        if frame_index % frame_skip == 0:
            timestamp_sec = frame_index / fps
            
            # Save teh frame as JPEG
            frame_path = os.path.join(frames_dir, f"frame_{frame_index}.jpg")

            # Record metadata
            frames_data.append({
                "frame_index": frame_index,
                "timestamp_sec": round(timestamp_sec, 2),
                "saved_path": frame_path,
            })

            saved_count += 1
            print(f" [{saved_count} frame {frame_index} @ {timestamp_sec:.2f}s]")

            # stop early if max_frames is set
            if max_frames is not None and saved_count >= max_frames:
                print(f"Reached max-frames limit ({max_frames}, stopping.)")
                break
        
        frame_index += 1

        # if cv.waitKey(20) & 0xFF==ord('d'): # if letter d is pressed break out loop
        #     break

    capture.release()
    cv.destroyAllWindows()

    result = {
        "video": {
            "path": input_path,
            "width": width,
            "height": height,
            "fps": round(fps, 4),
            "total_frames": total_frames,
            "duration_sec": round(duration_sec, 4),
        },
        "extraction": {
            "frame_skip": frame_skip,
            "max_frames": max_frames,
            "saved_count": saved_count,
        },
        "frames": frames_data,
    }

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nDone. {saved_count} frames --> {frames_dir}/")
    print(f"JSON --> {output_json}")

# Resizes to particular dimensions
def rescale_frame(frame, scale=0.75):
    # img, vids, and live vids OK
    width = int(frame.shape[1] * scale)
    height = int(frame.shape[0] * scale)
    
    dimensions = (width, height)

    return cv.resize(frame, dimensions, interpolation=cv.INTER_AREA)

def main():
    # args = parse_args()
    # process_video(
    #     input_path=args.input,
    #     output_json=args.output,
    #     frame_skip=args.frame_skip,
    #     max_frames=args.max_frames
    # )

    # TESTING detector
    for i in range(1, 27):
        print(i)

        frame = cv.imread(f"/Users/phonemaung/au/2026-1/csx3010/vids/ss/ss{i}.png")

        test_result = detect(
            frame,
            frame_number=0,
            timestamp_ms=0.0,
            method="color",
            highlight_color="purple"
        )

        print("===================================================")
        print(f" Screenshot: {i}")
        print("Enemies found:", len(test_result["enemy_positions"]))
        print(test_result["enemy_positions"])
        print("===================================================")

if __name__ == "__main__":
    main()