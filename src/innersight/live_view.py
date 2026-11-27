"""Live camera input and the preview window that shows it."""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import cv2
import numpy as np

from innersight.errors import CameraError

# The Qt that comes with opencv-python on Linux has the X11 platform plugin only. A Wayland
# desktop asks Qt for "wayland" first, which makes Qt print a warning before it falls back to
# X11. Qt reads this when the first window opens, so it is set before any window is shown.
os.environ["QT_QPA_PLATFORM"] = "xcb"

WINDOW_TITLE = "InnerSight"
QUIT_KEY = ord("q")
# What OpenCV reports, masked to one byte, when no key was pressed.
NO_KEY = 255
# What OpenCV reports as the full code when no key was pressed.
NO_KEY_CODE = -1
KEY_POLL_MILLISECONDS = 50

# The full key codes of the arrow keys differ between systems: Linux, Windows, macOS.
UP_KEYS = (65362, 2490368, 63232)
LEFT_KEYS = (65361, 2424832, 63234)
RIGHT_KEYS = (65363, 2555904, 63235)
DOWN_KEYS = (65364, 2621440, 63233)


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


def show_frame_for_key_code(frame_bgr: np.ndarray) -> int:
    """Show the frame in the preview window and return the full code of the key pressed in it.

    Unlike the one-byte code of show_frame, the full code tells the arrow keys apart from the
    letters. It is -1 when no key was pressed.
    """
    cv2.imshow(WINDOW_TITLE, frame_bgr)
    return cv2.waitKeyEx(1)


def show_frame_until_key(frame_bgr: np.ndarray) -> int:
    """Show the frame and wait until a key is pressed in the window; return the key's code.

    Closing the window counts as pressing the quit key.
    """
    return _show_until(frame_bgr, lambda: cv2.waitKey(KEY_POLL_MILLISECONDS) & 0xFF, NO_KEY)


def show_frame_until_key_code(frame_bgr: np.ndarray) -> int:
    """Show the frame and wait until a key is pressed in the window; return its full code.

    The full code tells the arrow keys apart from the letters. Closing the window counts as
    pressing the quit key.
    """
    return _show_until(frame_bgr, lambda: cv2.waitKeyEx(KEY_POLL_MILLISECONDS), NO_KEY_CODE)


def _show_until(frame_bgr: np.ndarray, read_key: Callable[[], int], no_key: int) -> int:
    cv2.imshow(WINDOW_TITLE, frame_bgr)
    while True:
        key = read_key()
        if key != no_key:
            return key
        if not _is_window_open():
            return QUIT_KEY


def close_window() -> None:
    cv2.destroyAllWindows()


def _is_window_open() -> bool:
    """OpenCV reports a closed window as not visible, or as an error once no window is left."""
    try:
        return cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) >= 1
    except cv2.error:
        return False


def _read_frames(capture: cv2.VideoCapture, camera_index: int) -> Iterator[np.ndarray]:
    while True:
        is_frame_read, frame = capture.read()
        if not is_frame_read:
            raise CameraError(f"Camera {camera_index} stopped delivering frames")
        yield frame
