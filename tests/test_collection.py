from datetime import datetime
from pathlib import Path

from fakes import BLACK_FRAME, ScriptedWindow

from innersight.cards import RANKS, Box, Card, CardColor, CardFace, Detection
from innersight.collection import (
    BACK_KEY,
    MIN_WINDOW_WIDTH,
    SAVE_KEY,
    SKIP_KEY,
    VALIDATION_ONE_IN,
    Candidate,
    CollectedExample,
    CollectResult,
    CollectSession,
    TrueCardPicker,
    candidates_from_game,
    save_collected,
)
from innersight.dataset import TRAIN_SPLIT, VALIDATION_SPLIT, CardDataset
from innersight.game import RoundFrame
from innersight.live_view import DOWN_KEYS, LEFT_KEYS, QUIT_KEY, RIGHT_KEYS, UP_KEYS

UP, LEFT, RIGHT, DOWN = UP_KEYS[0], LEFT_KEYS[0], RIGHT_KEYS[0], DOWN_KEYS[0]
UNUSED_KEY = ord("x")
RED_SEVEN = CardFace(CardColor.RED, "7")
BOX = Box(10, 5, 30, 40)
SESSION_START = datetime(2026, 11, 27, 20, 53, 1)


def read_as(face: CardFace) -> Card:
    return Card(Detection(face.rank, confidence=0.6, box=BOX), face.color)


def make_candidates(count: int) -> list[Candidate]:
    return [
        Candidate(f"game_r{number}", BLACK_FRAME, read_as(RED_SEVEN), RED_SEVEN)
        for number in range(1, count + 1)
    ]


def collect(candidates: list[Candidate], *keys: int) -> CollectResult:
    return CollectSession(ScriptedWindow(*keys)).run(candidates)


def saved_labels(result: CollectResult) -> list[str]:
    return [example.face.label for example in result.saved]


def make_example(key: str, face: CardFace = RED_SEVEN) -> CollectedExample:
    return CollectedExample(key, BLACK_FRAME, BOX, face)


def test_picker_starts_at_the_card_the_detector_read() -> None:
    picker = TrueCardPicker(RED_SEVEN)

    assert picker.face == RED_SEVEN


def test_picker_steps_to_the_next_rank_and_keeps_the_color() -> None:
    picker = TrueCardPicker(RED_SEVEN)

    picker.step_rank(1)

    assert picker.face == CardFace(CardColor.RED, "8")


def test_picker_goes_around_from_the_last_rank_to_the_first() -> None:
    picker = TrueCardPicker(CardFace(CardColor.WILD, RANKS[-1]))

    picker.step_rank(1)

    assert picker.face.rank == RANKS[0]


def test_picker_goes_around_from_the_first_color_to_the_last() -> None:
    picker = TrueCardPicker(RED_SEVEN)

    picker.step_color(-1)

    assert picker.face == CardFace(CardColor.BLUE, "7")


def test_a_wild_rank_is_wild_whatever_color_was_chosen() -> None:
    picker = TrueCardPicker(CardFace(CardColor.BLUE, "+2"))

    picker.step_rank(1)

    assert picker.face == CardFace(CardColor.WILD, "wild")


def test_color_steps_do_nothing_for_a_wild_card() -> None:
    picker = TrueCardPicker(CardFace(CardColor.BLUE, "+2"))
    picker.step_rank(1)

    picker.step_color(1)
    picker.step_rank(-1)

    assert picker.face == CardFace(CardColor.BLUE, "+2")


def test_picker_gives_the_back_its_own_color() -> None:
    picker = TrueCardPicker(CardFace(CardColor.WILD, "+4"))

    picker.step_rank(1)

    assert picker.face == CardFace(CardColor.BACK, "back")


def test_saves_a_card_as_it_was_read_when_nothing_is_changed() -> None:
    result = collect(make_candidates(1), SAVE_KEY)

    assert saved_labels(result) == ["red 7"]


def test_saves_a_card_under_the_rank_and_color_chosen_with_the_arrow_keys() -> None:
    result = collect(make_candidates(1), UP, UP, RIGHT, SAVE_KEY)

    assert saved_labels(result) == ["yellow 9"]


def test_steps_back_through_the_ranks_and_colors_with_the_other_arrow_keys() -> None:
    result = collect(make_candidates(1), DOWN, LEFT, SAVE_KEY)

    assert saved_labels(result) == ["blue 6"]


def test_keeps_the_box_the_card_was_read_in() -> None:
    result = collect(make_candidates(1), SAVE_KEY)

    assert result.saved[0].box == BOX


def test_skips_a_card_without_saving_it() -> None:
    candidates = make_candidates(2)

    result = collect(candidates, SKIP_KEY, SAVE_KEY)

    assert [example.key for example in result.saved] == ["game_r2"]
    assert result.skipped == [candidates[0]]


def test_saving_a_card_again_after_going_back_replaces_its_true_card() -> None:
    result = collect(make_candidates(2), SAVE_KEY, BACK_KEY, UP, SAVE_KEY, SAVE_KEY)

    assert saved_labels(result) == ["red 8", "red 7"]


def test_skipping_a_card_after_going_back_takes_it_out_of_the_saved_ones() -> None:
    result = collect(make_candidates(2), SAVE_KEY, BACK_KEY, SKIP_KEY, SKIP_KEY)

    assert result.saved == []


def test_quit_key_ends_the_session_and_keeps_what_was_saved() -> None:
    result = collect(make_candidates(3), SAVE_KEY, QUIT_KEY)

    assert [example.key for example in result.saved] == ["game_r1"]
    assert result.skipped == []


def test_stays_on_the_same_card_when_another_key_is_pressed() -> None:
    window = ScriptedWindow(UNUSED_KEY, SAVE_KEY)

    CollectSession(window).run(make_candidates(1))

    assert window.frames_shown == 2


def test_shows_a_narrow_frame_in_a_window_wide_enough_for_the_text() -> None:
    window = ScriptedWindow(SAVE_KEY)

    CollectSession(window).run(make_candidates(1))

    assert window.last_frame is not None
    assert window.last_frame.shape[1] == MIN_WINDOW_WIDTH


def test_makes_a_candidate_of_every_round_that_starts_at_the_card_read() -> None:
    blue_skip = CardFace(CardColor.BLUE, "skip")
    round_frames = [
        RoundFrame(BLACK_FRAME, read_as(RED_SEVEN)),
        RoundFrame(BLACK_FRAME, read_as(blue_skip)),
    ]

    candidates = candidates_from_game(round_frames, SESSION_START)

    assert [candidate.suggested for candidate in candidates] == [RED_SEVEN, blue_skip]
    assert [candidate.key for candidate in candidates] == [
        "game_20261127T205301_r1",
        "game_20261127T205301_r2",
    ]


def test_names_an_example_after_its_true_card_and_where_it_comes_from() -> None:
    example = make_example("game_20261127T205301_r3", CardFace(CardColor.WILD, "+4"))

    assert example.name == "wild_+4_game_20261127T205301_r3"


def test_holds_back_about_one_example_in_five_for_validation() -> None:
    splits = [make_example(f"game_r{number}").split for number in range(1000)]

    held_back_share = splits.count(VALIDATION_SPLIT) / len(splits)
    assert abs(held_back_share - 1 / VALIDATION_ONE_IN) < 0.05


def test_puts_an_example_in_the_same_split_whatever_its_true_card_is() -> None:
    as_seven = make_example("game_r1", RED_SEVEN)
    as_wild = make_example("game_r1", CardFace(CardColor.WILD, "wild"))

    assert as_seven.split == as_wild.split


def test_writes_an_example_into_its_split_labeled_with_the_true_rank(tmp_path: Path) -> None:
    example = make_example("game_r1", CardFace(CardColor.GREEN, "reverse"))
    dataset = CardDataset(tmp_path)

    save_collected(dataset, [example])

    _, cards = dataset.read_example(example.split, "green_reverse_game_r1")
    assert [card.rank for card in cards] == ["reverse"]
    assert example.split in (TRAIN_SPLIT, VALIDATION_SPLIT)


def test_writes_the_dataset_config_with_the_examples(tmp_path: Path) -> None:
    save_collected(CardDataset(tmp_path), [make_example("game_r1")])

    assert (tmp_path / "data.yaml").is_file()
