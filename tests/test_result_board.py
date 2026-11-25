from innersight.cards import CardColor, CardFace
from innersight.guessing import GuessOutcome, GuessRound
from innersight.result_board import BOARD_WIDTH, draw_result_board, result_rows

ROUNDS = [
    GuessRound(CardFace(CardColor.RED, "7"), 0.934, GuessOutcome.BOTH_RIGHT),
    GuessRound(CardFace(CardColor.BLUE, "skip"), 0.61, GuessOutcome.MISS),
    GuessRound(CardFace(CardColor.WILD, "+4"), 0.8, GuessOutcome.MISS),
    GuessRound(CardFace(CardColor.GREEN, "2"), 0.75, GuessOutcome.COLOR_RIGHT),
]


def test_counts_every_outcome_with_its_share_of_the_cards() -> None:
    rows = result_rows(ROUNDS)

    assert ("", "both right", "1", "25%") in rows
    assert ("", "color right", "1", "25%") in rows
    assert ("", "rank right", "0", "0%") in rows
    assert ("", "miss", "2", "50%") in rows


def test_lists_every_card_with_the_confidence_of_the_model_and_the_outcome() -> None:
    rows = result_rows(ROUNDS)

    assert rows[-4:] == [
        ("1", "red 7", "93%", "both right"),
        ("2", "blue skip", "61%", "miss"),
        ("3", "wild +4", "80%", "miss"),
        ("4", "green 2", "75%", "color right"),
    ]


def test_draws_a_board_that_grows_with_the_number_of_cards() -> None:
    short_board = draw_result_board(ROUNDS[:1])
    long_board = draw_result_board(ROUNDS)

    assert short_board.shape[1] == long_board.shape[1] == BOARD_WIDTH
    assert long_board.shape[0] > short_board.shape[0]
    assert long_board.any()
