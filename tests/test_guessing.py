from innersight.announcement import STABLE_FRAME_COUNT
from innersight.cards import BACK_RANK, Box, Card, CardColor, Detection
from innersight.guessing import (
    CORRECTION_SECONDS,
    FIRST_CARD_PHRASE,
    LAST_CARD_PHRASE,
    NEXT_CARD_PHRASE,
    NO_ANSWER_PHRASE,
    NO_CARD_PHRASE,
    GuessingSession,
    GuessOutcome,
    GuessRound,
    count_outcomes,
)

NO_CARDS: list[Card] = []


def make_card(color: CardColor, rank: str, confidence: float = 0.9) -> Card:
    return Card(Detection(rank=rank, confidence=confidence, box=Box(0, 0, 10, 10)), color)


RED_SEVEN = make_card(CardColor.RED, "7", confidence=0.8)
BLUE_SKIP = make_card(CardColor.BLUE, "skip")
UNSURE_GREEN_TWO = make_card(CardColor.GREEN, "2", confidence=0.6)
CARD_BACK = make_card(CardColor.BACK, BACK_RANK)


class FakeClock:
    """A clock that stands still until a test moves it."""

    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds


def start_session(
    card_count: int = 2, clock: FakeClock | None = None
) -> tuple[GuessingSession, list[str]]:
    """Start a session and forget the greeting, so a test sees only what it causes."""
    spoken: list[str] = []
    session = GuessingSession(card_count, spoken.append, clock or FakeClock())
    spoken.clear()
    return session, spoken


def hold_up(session: GuessingSession, card: Card) -> None:
    """Take the last card away and hold up this one until it settles."""
    for cards in (NO_CARDS, [card]):
        for _ in range(STABLE_FRAME_COUNT):
            session.observe(cards)


def play_round(session: GuessingSession, card: Card, outcome: GuessOutcome) -> None:
    hold_up(session, card)
    session.give_answer(outcome)
    session.lock_in()


def test_asks_for_the_first_card_when_the_session_starts() -> None:
    spoken: list[str] = []

    GuessingSession(2, spoken.append)

    assert spoken == [FIRST_CARD_PHRASE]


def test_reads_a_card_aloud_once_it_has_settled_in_view() -> None:
    session, spoken = start_session()

    hold_up(session, RED_SEVEN)

    assert spoken == ["red seven"]


def test_says_which_answer_was_given() -> None:
    session, spoken = start_session()
    hold_up(session, RED_SEVEN)

    session.give_answer(GuessOutcome.COLOR_RIGHT)

    assert spoken[-1] == "color right"


def test_counts_only_the_last_answer_given_before_locking_in() -> None:
    session, _ = start_session()
    hold_up(session, RED_SEVEN)

    session.give_answer(GuessOutcome.MISS)
    session.give_answer(GuessOutcome.COLOR_RIGHT)
    session.give_answer(GuessOutcome.BOTH_RIGHT)
    session.lock_in()

    assert [played_round.outcome for played_round in session.rounds] == [GuessOutcome.BOTH_RIGHT]


def test_logs_the_card_the_model_read_and_how_sure_it_was() -> None:
    session, _ = start_session()
    hold_up(session, RED_SEVEN)
    session.give_answer(GuessOutcome.MISS)

    locked_round = session.lock_in()

    assert locked_round == GuessRound(RED_SEVEN.face, 0.8, GuessOutcome.MISS)


def test_says_an_answer_without_counting_it_while_no_card_is_read() -> None:
    session, spoken = start_session()

    session.give_answer(GuessOutcome.RANK_RIGHT)
    hold_up(session, RED_SEVEN)

    assert spoken[0] == "rank right"
    assert session.answer is None


def test_does_not_lock_in_before_a_card_is_read() -> None:
    session, spoken = start_session()

    locked_round = session.lock_in()

    assert locked_round is None
    assert spoken == [NO_CARD_PHRASE]


def test_does_not_lock_in_before_an_answer_is_given() -> None:
    session, spoken = start_session()
    hold_up(session, RED_SEVEN)

    locked_round = session.lock_in()

    assert locked_round is None
    assert spoken[-1] == NO_ANSWER_PHRASE


def test_asks_for_the_next_card_after_locking_in() -> None:
    session, spoken = start_session(card_count=3)

    play_round(session, RED_SEVEN, GuessOutcome.MISS)

    assert spoken[-1] == NEXT_CARD_PHRASE


def test_asks_for_the_last_card_when_one_card_is_left() -> None:
    session, spoken = start_session(card_count=3)
    play_round(session, RED_SEVEN, GuessOutcome.MISS)

    play_round(session, BLUE_SKIP, GuessOutcome.MISS)

    assert spoken[-1] == LAST_CARD_PHRASE


def test_reports_the_card_that_starts_a_round_on_the_frame_it_settles() -> None:
    session, _ = start_session()
    frames_before_settling = [session.observe([RED_SEVEN]) for _ in range(STABLE_FRAME_COUNT - 1)]

    round_card = session.observe([RED_SEVEN])

    assert frames_before_settling == [None] * (STABLE_FRAME_COUNT - 1)
    assert round_card == RED_SEVEN


def test_corrects_the_card_of_the_round_when_a_surer_reading_settles() -> None:
    session, spoken = start_session()
    hold_up(session, RED_SEVEN)

    hold_up(session, BLUE_SKIP)

    assert session.card == BLUE_SKIP
    assert spoken == ["red seven", "Correction. blue skip"]


def test_reports_the_corrected_card_on_the_frame_it_settles() -> None:
    session, _ = start_session()
    hold_up(session, RED_SEVEN)
    for _ in range(STABLE_FRAME_COUNT - 1):
        session.observe([BLUE_SKIP])

    round_card = session.observe([BLUE_SKIP])

    assert round_card == BLUE_SKIP


def test_drops_the_answer_given_to_a_card_that_is_corrected() -> None:
    session, _ = start_session()
    hold_up(session, RED_SEVEN)
    session.give_answer(GuessOutcome.BOTH_RIGHT)

    hold_up(session, BLUE_SKIP)

    assert session.answer is None


def test_keeps_the_card_of_the_round_when_the_other_reading_is_less_sure() -> None:
    session, spoken = start_session()
    hold_up(session, RED_SEVEN)

    hold_up(session, UNSURE_GREEN_TWO)

    assert session.card == RED_SEVEN
    assert spoken == ["red seven"]


def test_corrects_the_card_until_the_time_for_corrections_is_up() -> None:
    clock = FakeClock()
    session, _ = start_session(clock=clock)
    hold_up(session, RED_SEVEN)

    clock.seconds += CORRECTION_SECONDS
    hold_up(session, BLUE_SKIP)

    assert session.card == BLUE_SKIP


def test_keeps_the_card_of_the_round_once_the_time_for_corrections_is_up() -> None:
    clock = FakeClock()
    session, spoken = start_session(clock=clock)
    hold_up(session, RED_SEVEN)

    clock.seconds += CORRECTION_SECONDS + 0.1
    hold_up(session, BLUE_SKIP)

    assert session.card == RED_SEVEN
    assert spoken == ["red seven"]


def test_does_not_correct_a_card_to_the_back_of_a_card() -> None:
    session, spoken = start_session()
    hold_up(session, RED_SEVEN)

    hold_up(session, CARD_BACK)

    assert session.card == RED_SEVEN
    assert spoken == ["red seven"]


def test_reads_the_same_card_again_as_the_next_round_after_it_was_taken_away() -> None:
    session, _ = start_session()
    play_round(session, RED_SEVEN, GuessOutcome.MISS)

    hold_up(session, RED_SEVEN)

    assert session.card == RED_SEVEN


def test_does_not_start_the_next_round_with_the_card_still_in_view() -> None:
    session, _ = start_session()
    play_round(session, RED_SEVEN, GuessOutcome.MISS)

    for _ in range(STABLE_FRAME_COUNT * 3):
        session.observe([RED_SEVEN])

    assert session.card is None


def test_reads_the_back_of_a_card_aloud_without_starting_a_round() -> None:
    session, spoken = start_session()

    hold_up(session, CARD_BACK)

    assert spoken == ["card back"]
    assert session.card is None


def test_reports_no_card_for_the_back_of_a_card() -> None:
    session, _ = start_session()
    for _ in range(STABLE_FRAME_COUNT - 1):
        session.observe([CARD_BACK])

    round_card = session.observe([CARD_BACK])

    assert round_card is None


def test_finishes_after_the_chosen_number_of_cards() -> None:
    session, _ = start_session(card_count=2)

    play_round(session, RED_SEVEN, GuessOutcome.MISS)
    is_finished_after_one_card = session.is_finished
    play_round(session, BLUE_SKIP, GuessOutcome.BOTH_RIGHT)

    assert not is_finished_after_one_card
    assert session.is_finished


def test_says_the_result_when_the_session_finishes() -> None:
    session, spoken = start_session(card_count=2)

    play_round(session, RED_SEVEN, GuessOutcome.MISS)
    play_round(session, BLUE_SKIP, GuessOutcome.BOTH_RIGHT)

    expected = "Session finished. both right 1, color right 0, rank right 0, miss 1."
    assert spoken[-1] == expected


def test_reads_no_more_cards_after_the_session_finished() -> None:
    session, spoken = start_session(card_count=1)
    play_round(session, RED_SEVEN, GuessOutcome.MISS)
    spoken.clear()

    hold_up(session, BLUE_SKIP)

    assert spoken == []


def test_counts_every_outcome_even_one_that_never_happened() -> None:
    rounds = [
        GuessRound(RED_SEVEN.face, 0.8, GuessOutcome.COLOR_RIGHT),
        GuessRound(BLUE_SKIP.face, 0.9, GuessOutcome.COLOR_RIGHT),
    ]

    assert count_outcomes(rounds) == {
        GuessOutcome.BOTH_RIGHT: 0,
        GuessOutcome.COLOR_RIGHT: 2,
        GuessOutcome.RANK_RIGHT: 0,
        GuessOutcome.MISS: 0,
    }
