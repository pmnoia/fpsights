import cv2 as cv

def read_frames(video_path, frame_skip=5, max_frames=None):
    """
    Reads frames from a video.
    frame_skip=5 means process every 5th frame
    """

    video = cv.VideoCapture(video_path)

    if not video.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")
    
    frame_number = 0 
    processed_count = 0

    while True:
        success, frame = video.read()

        if not success:
            break

        if frame_number % frame_skip == 0:
            yield frame_number, frame
            processed_count += 1

        frame_number += 1

        if max_frames is not None and processed_count >= max_frames:
            break

    video.release()