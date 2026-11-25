# InnerSight

Recognizing the UNO card held up to a camera and saying it aloud, for a player who cannot see
the card.

## Language

**Reading**:
What the camera makes of one card in one frame: its rank, its color, and where it is.
_Avoid_: Detection (that is the rank and the box only), prediction

**Readable card**:
A card whose color could be read. A card whose color could not be read is not a card that
exists, so it is never announced or guessed.
_Avoid_: Valid card, known card

**Surest card**:
Of the cards in one frame, the one whose rank the detector is most confident of. Only this
card counts.
_Avoid_: Best card, top card, main card

**Settle**:
A reading settles when it has stayed the same for several frames in a row. A card is announced
only once it has settled, and counts as taken away only once its absence has settled.
_Avoid_: Stabilize, confirm, debounce

**Too close**:
A card is too close when it is as tall or as wide as the frame, so part of it may be out of
view.
_Avoid_: Clipped, cut off, out of frame
