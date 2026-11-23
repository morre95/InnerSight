"""Failures InnerSight reports to the user as a message instead of a traceback."""


class InnerSightError(Exception):
    pass


class CameraError(InnerSightError):
    pass


class DatasetWriteError(InnerSightError):
    pass


class SpeechError(InnerSightError):
    pass
