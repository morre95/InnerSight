# The color reading is tuned per camera, not shared

The desktop color reading (`color.py`) and the phone color reading (`color_classifier.dart`)
use different hue ranges and thresholds on purpose. The desktop numbers are tuned for one
webcam in a room lit by a monitor; the phone camera gives other colors and reads cards well
with its own numbers. So a change to the numbers of one does not need a matching change to
the other, and one calibration is not exported for both.

The steps are another matter. Removing the tint of the light (white balance from the brightest
pixels of the box) is needed on both: a log from the phone in monitor light showed the white
of the card counted as blue, so that no color dominated, and the step fixed it. Splitting
the olive hues by brightness is needed on both too: the images in `datasets/phone-cards`
showed green cards in the hues of yellow, more so out of focus, while their brightness kept
them apart. Both measure that brightness against the white of the card: a fixed level
called a well-lit green card yellow and a dimly lit yellow card green. Both also take a pixel
for black, not colored, when it is dark as a share of that white: with a fixed level,
darkened copies of the recorded images of both cameras lost their color. The desktop has
further steps the phone lacks (a
stricter saturation for blue, red reaching down into purple, and saturation limits that
are lowered when bright light behind the card washes it out, measured on
`datasets/own-cards-blurry`). Port one of them only when a
log or recorded images from the phone show it is needed, and check in daylight that it does
not make the good case worse.

The other logic that exists on both sides (watcher, announcer, guessing session, spoken names)
is still changed on both sides together.
