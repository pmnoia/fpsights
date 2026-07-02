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

def read_frames(input_path, frame_skip=3, max_frames=None):
    capture = cv.VideoCapture(input_path)

    if not capture.isOpened():
        print(f"SORRY! Could not open video: {input_path}")
        sys.exit(1)
    fps = capture.get(cv.CAP_PROP_FPS)
    frame_num = 0 # index of every frame read from the video
    count = 0 # count of frames actually yielded

    while True:
        isTrue, frame = capture.read()
        if not isTrue or frame is None:
            break
        
        if frame_num % frame_skip == 0:
            if fps > 0:
                #timestamp_sec = frame_index / fps
                timestamp_ms = (frame_num % fps) * 1000
            else:
                timestamp_ms = 0.0
            yield frame, frame_num, round(timestamp_ms, 2)

            count += 1
        
        frame_num += 1
    
    capture.release()