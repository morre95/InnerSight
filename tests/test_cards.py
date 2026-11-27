import pytest

from innersight.cards import CARD_BACK, DECK, RANKS, CardColor, CardFace, fixed_color


def test_deck_holds_57_distinct_faces() -> None:
    assert len(DECK) == len(set(DECK)) == 56


def test_every_face_in_the_deck_has_a_detector_class() -> None:
    assert {face.rank for face in DECK} | {CARD_BACK.rank} == set(RANKS)


def test_back_is_not_a_design_in_the_deck() -> None:
    assert CARD_BACK not in DECK


def test_ranks_keep_the_class_ids_of_labels_that_are_already_recorded() -> None:
    assert [RANKS.index(rank) for rank in ("0", "+4", "back", "customizable")] == [0, 14, 15, 17]


@pytest.mark.parametrize(
    ("face", "expected_label"),
    [
        (CardFace(CardColor.RED, "7"), "red 7"),
        (CardFace(CardColor.BLUE, "+2"), "blue +2"),
        (CardFace(CardColor.WILD, "wild"), "wild"),
        (CardFace(CardColor.WILD, "+4"), "wild +4"),
        (CardFace(CardColor.WILD, "shuffle"), "wild shuffle"),
        (CardFace(CardColor.WILD, "customizable"), "wild customizable"),
        (CARD_BACK, "back"),
    ],
)
def test_labels_a_face_by_color_and_rank(face: CardFace, expected_label: str) -> None:
    assert face.label == expected_label


@pytest.mark.parametrize(
    ("rank", "expected_color"),
    [("wild", CardColor.WILD), ("+4", CardColor.WILD), ("back", CardColor.BACK), ("7", None)],
)
def test_only_a_wild_rank_and_the_back_have_a_color_of_their_own(
    rank: str, expected_color: CardColor | None
) -> None:
    assert fixed_color(rank) == expected_color
