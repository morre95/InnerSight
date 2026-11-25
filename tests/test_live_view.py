import os

import innersight.live_view  # noqa: F401, importing it is what sets the platform


def test_asks_qt_for_the_only_platform_plugin_that_opencv_comes_with() -> None:
    assert os.environ["QT_QPA_PLATFORM"] == "xcb"
