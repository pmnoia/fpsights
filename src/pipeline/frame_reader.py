import sys
import cv2 as cv

def get_video_info(input_path):
    # Open video and return metadata as dict
    capture = cv.VideoCapture(input_path)
    if not capture.isOpened():
        print(f"SORRY! Could not open video: {input_path}")
        sys.exit(1)
    
    fps = capture.get(cv.CAP_PROP_FPS)
    width = int(capture.get(cv.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(capture.get(cv.CAP_PROP_FRAME_COUNT))

    capture.release()
    return fps, width, height, total_frames

def read_frames(input_path, frame_skip=1, max_frames=None, start_time=0):
    if frame_skip < 1:
        raise ValueError("frame_skip must be 1 or greater")
    if max_frames is not None and max_frames < 1:
        raise ValueError("max_frames must be 1 or greater")
    if start_time < 0:
        raise ValueError("start_time cannot be negative")

    capture = cv.VideoCapture(input_path)

    if not capture.isOpened():
        print(f"SORRY! Could not open video: {input_path}")
        sys.exit(1)
    fps = capture.get(cv.CAP_PROP_FPS)

    # Jump to start_time if given
    if start_time > 0:
        capture.set(cv.CAP_PROP_POS_MSEC, start_time * 1000)
    frame_num = int(capture.get(cv.CAP_PROP_POS_FRAMES)) # index of every frame read from the video
    count = 0 # count of frames actually yielded

    while True:
        isTrue, frame = capture.read()
        if not isTrue or frame is None:
            break
        
        if frame_num % frame_skip == 0:
            if fps > 0:
                #timestamp_sec = frame_index / fps
                timestamp_ms = (frame_num / fps) * 1000
            else:
                timestamp_ms = 0.0
            yield frame, frame_num, round(timestamp_ms, 2)

            count += 1
            if max_frames is not None and count >= max_frames:
                break
        
        frame_num += 1
    
    capture.release()
