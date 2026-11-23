import numpy as np

from innersight.annotation import draw_cards
from innersight.cards import Box, Card, CardColor, Detection


def test_draws_on_a_copy_and_leaves_the_frame_untouched() -> None:
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    card = Card(Detection(rank="7", confidence=0.9, box=Box(10, 30, 60, 90)), CardColor.RED)

    annotated = draw_cards(frame, [card])

    assert annotated.any()
    assert not frame.any()
