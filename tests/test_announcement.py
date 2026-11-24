import pytest

from innersight.announcement import SPOKEN_RANKS, STABLE_FRAME_COUNT, CardAnnouncer, spoken_name
from innersight.cards import CARD_BACK, RANKS, Box, Card, CardColor, CardFace, Detection

NO_CARDS: list[Card] = []


def make_card(color: CardColor, rank: str, confidence: float = 0.9) -> Card:
    return Card(Detection(rank=rank, confidence=confidence, box=Box(0, 0, 10, 10)), color)


RED_SEVEN = make_card(CardColor.RED, "7")
BLUE_SKIP = make_card(CardColor.BLUE, "skip")


def make_announcer() -> tuple[CardAnnouncer, list[str]]:
    spoken: list[str] = []
    return CardAnnouncer(spoken.append), spoken


def show(announcer: CardAnnouncer, cards: list[Card], frame_count: int) -> None:
    for _ in range(frame_count):
        announcer.observe(cards)


@pytest.mark.parametrize(
    ("face", "expected_words"),
    [
        (CardFace(CardColor.RED, "7"), "red seven"),
        (CardFace(CardColor.BLUE, "+2"), "blue draw two"),
        (CardFace(CardColor.WILD, "wild"), "wild"),
        (CardFace(CardColor.WILD, "+4"), "wild draw four"),
        (CARD_BACK, "card back"),
    ],
)
def test_speaks_the_color_and_then_the_rank_in_words(face: CardFace, expected_words: str) -> None:
    assert spoken_name(face) == expected_words


def test_speaks_an_unknown_rank_as_it_is_written() -> None:
    assert spoken_name(CardFace(CardColor.GREEN, "color_change")) == "green color_change"


def test_every_rank_has_spoken_words() -> None:
    assert set(RANKS) == set(SPOKEN_RANKS)


def test_announces_a_card_once_it_has_settled_in_view() -> None:
    announcer, spoken = make_announcer()

    show(announcer, [RED_SEVEN], STABLE_FRAME_COUNT)

    assert spoken == ["red seven"]


def test_stays_quiet_until_the_card_has_settled() -> None:
    announcer, spoken = make_announcer()

    show(announcer, [RED_SEVEN], STABLE_FRAME_COUNT - 1)

    assert spoken == []


def test_does_not_repeat_a_card_that_stays_in_view() -> None:
    announcer, spoken = make_announcer()

    show(announcer, [RED_SEVEN], STABLE_FRAME_COUNT * 10)

    assert spoken == ["red seven"]


def test_announces_the_same_card_again_after_it_was_taken_away() -> None:
    announcer, spoken = make_announcer()

    show(announcer, [RED_SEVEN], STABLE_FRAME_COUNT)
    show(announcer, NO_CARDS, STABLE_FRAME_COUNT)
    show(announcer, [RED_SEVEN], STABLE_FRAME_COUNT)

    assert spoken == ["red seven", "red seven"]


def test_does_not_repeat_a_card_after_a_brief_dropout() -> None:
    announcer, spoken = make_announcer()

    show(announcer, [RED_SEVEN], STABLE_FRAME_COUNT)
    show(announcer, NO_CARDS, STABLE_FRAME_COUNT - 1)
    show(announcer, [RED_SEVEN], STABLE_FRAME_COUNT)

    assert spoken == ["red seven"]


def test_announces_a_new_card_that_replaces_the_old_one() -> None:
    announcer, spoken = make_announcer()

    show(announcer, [RED_SEVEN], STABLE_FRAME_COUNT)
    show(announcer, [BLUE_SKIP], STABLE_FRAME_COUNT)

    assert spoken == ["red seven", "blue skip"]


def test_stays_quiet_while_the_reading_keeps_changing() -> None:
    announcer, spoken = make_announcer()

    for _ in range(STABLE_FRAME_COUNT):
        announcer.observe([RED_SEVEN])
        announcer.observe([BLUE_SKIP])

    assert spoken == []


def test_announces_the_most_confident_card_when_several_are_in_view() -> None:
    announcer, spoken = make_announcer()
    faint_card = make_card(CardColor.GREEN, "2", confidence=0.5)
    clear_card = make_card(CardColor.YELLOW, "reverse", confidence=0.95)

    show(announcer, [faint_card, clear_card], STABLE_FRAME_COUNT)

    assert spoken == ["yellow reverse"]
