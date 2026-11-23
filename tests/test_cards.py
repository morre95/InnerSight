import pytest

from innersight.cards import DECK, CardColor, CardFace


def test_deck_holds_54_distinct_faces() -> None:
    assert len(DECK) == len(set(DECK)) == 54


@pytest.mark.parametrize(
    ("face", "expected_label"),
    [
        (CardFace(CardColor.RED, "7"), "red 7"),
        (CardFace(CardColor.BLUE, "+2"), "blue +2"),
        (CardFace(CardColor.WILD, "wild"), "wild"),
        (CardFace(CardColor.WILD, "+4"), "wild +4"),
    ],
)
def test_labels_a_face_by_color_and_rank(face: CardFace, expected_label: str) -> None:
    assert face.label == expected_label
