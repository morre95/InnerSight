import pytest

from innersight.cards import CARD_BACK, DECK, RANKS, CardColor, CardFace


def test_deck_holds_54_distinct_faces() -> None:
    assert len(DECK) == len(set(DECK)) == 54


def test_back_is_not_a_design_in_the_deck() -> None:
    assert CARD_BACK not in DECK


def test_back_is_the_last_detector_class() -> None:
    assert RANKS[-1] == CARD_BACK.rank


@pytest.mark.parametrize(
    ("face", "expected_label"),
    [
        (CardFace(CardColor.RED, "7"), "red 7"),
        (CardFace(CardColor.BLUE, "+2"), "blue +2"),
        (CardFace(CardColor.WILD, "wild"), "wild"),
        (CardFace(CardColor.WILD, "+4"), "wild +4"),
        (CARD_BACK, "back"),
    ],
)
def test_labels_a_face_by_color_and_rank(face: CardFace, expected_label: str) -> None:
    assert face.label == expected_label
