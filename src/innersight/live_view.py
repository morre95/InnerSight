"""Live camera input and the preview window that shows it."""

from collections.abc import Iterator
from contextlib import contextmanager

import cv2
import numpy as np

from innersight.errors import CameraError

WINDOW_TITLE = "InnerSight"
QUIT_KEY = ord("q")


@contextmanager
def open_camera(camera_index: int) -> Iterator[Iterator[np.ndarray]]:
    """Yield the camera's frames; release the camera and close the window afterwards."""
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        raise CameraError(f"Could not open camera {camera_index}")
    try:
        yield _read_frames(capture, camera_index)
    finally:
        capture.release()
        cv2.destroyAllWindows()


def show_frame(frame_bgr: np.ndarray) -> int:
    """Show the frame in the preview window and return the code of the key pressed in it.

    The code is 255 when no key was pressed.
    """
    cv2.imshow(WINDOW_TITLE, frame_bgr)
    return cv2.waitKey(1) & 0xFF


def _read_frames(capture: cv2.VideoCapture, camera_index: int) -> Iterator[np.ndarray]:
    while True:
        is_frame_read, frame = capture.read()
        if not is_frame_read:
            raise CameraError(f"Camera {camera_index} stopped delivering frames")
        yield frame
