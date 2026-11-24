import pytest

from innersight.cards import CARD_BACK, DECK, RANKS, CardColor, CardFace


def test_deck_holds_57_distinct_faces() -> None:
    assert len(DECK) == len(set(DECK)) == 57


def test_every_face_in_the_deck_has_a_detector_class() -> None:
    assert {face.rank for face in DECK} | {CARD_BACK.rank} == set(RANKS)


def test_back_is_not_a_design_in_the_deck() -> None:
    assert CARD_BACK not in DECK


def test_ranks_keep_the_class_ids_of_labels_that_are_already_recorded() -> None:
    assert [RANKS.index(rank) for rank in ("0", "+4", "back", "joker")] == [0, 14, 15, 17]


@pytest.mark.parametrize(
    ("face", "expected_label"),
    [
        (CardFace(CardColor.RED, "7"), "red 7"),
        (CardFace(CardColor.BLUE, "+2"), "blue +2"),
        (CardFace(CardColor.WILD, "wild"), "wild"),
        (CardFace(CardColor.WILD, "+4"), "wild +4"),
        (CardFace(CardColor.WILD, "shuffle"), "wild shuffle"),
        (CardFace(CardColor.WILD, "joker"), "wild joker"),
        (CardFace(CardColor.WILD, "customizable"), "wild customizable"),
        (CARD_BACK, "back"),
    ],
)
def test_labels_a_face_by_color_and_rank(face: CardFace, expected_label: str) -> None:
    assert face.label == expected_label
