# The color reading is tuned per camera, not shared

The desktop color reading (`color.py`) and the phone color reading (`color_classifier.dart`)
are deliberately separate: they use different hue ranges and thresholds, and the desktop one
has extra steps (white balance, the olive band split by brightness, a stricter saturation for
blue) that the phone lacks. Those steps correct for one webcam in a room lit by a monitor. The
phone camera balances white itself and reads colors well with the simpler reading, so porting
the desktop calibration to the phone, or exporting one calibration for both, risks making the
phone worse.

A change to one color reading therefore does not need a matching change to the other. The
other logic that exists on both sides (watcher, announcer, guessing session, spoken names) is
still changed on both sides together.
