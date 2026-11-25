import csv
from datetime import datetime
from pathlib import Path

import pytest

from innersight.cards import CardColor, CardFace
from innersight.errors import GuessLogWriteError
from innersight.guess_log import GuessLog
from innersight.guessing import GuessOutcome, GuessRound

SESSION_START = datetime(2026, 11, 25, 18, 30)
RED_SEVEN_MISSED = GuessRound(CardFace(CardColor.RED, "7"), 0.8766, GuessOutcome.MISS)
WILD_GUESSED = GuessRound(CardFace(CardColor.WILD, "+4"), 0.5, GuessOutcome.BOTH_RIGHT)


def read_rows(log_file: Path) -> list[dict[str, str]]:
    with log_file.open(newline="") as rows:
        return list(csv.DictReader(rows))


def test_logs_the_card_its_confidence_and_the_outcome(tmp_path: Path) -> None:
    log_file = tmp_path / "guesses.csv"

    GuessLog(log_file, SESSION_START).append(1, RED_SEVEN_MISSED)

    assert read_rows(log_file) == [
        {
            "session": "2026-11-25T18:30:00",
            "card_number": "1",
            "card": "red 7",
            "confidence": "0.877",
            "outcome": "miss",
        }
    ]


def test_adds_a_later_session_below_the_earlier_ones(tmp_path: Path) -> None:
    log_file = tmp_path / "guesses.csv"
    GuessLog(log_file, SESSION_START).append(1, RED_SEVEN_MISSED)

    GuessLog(log_file, datetime(2026, 11, 26, 9, 0)).append(1, WILD_GUESSED)

    assert [row["card"] for row in read_rows(log_file)] == ["red 7", "wild +4"]


def test_creates_the_directory_of_the_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "guesses.csv"

    GuessLog(log_file, SESSION_START).append(1, RED_SEVEN_MISSED)

    assert log_file.is_file()


def test_reports_a_log_file_that_cannot_be_written(tmp_path: Path) -> None:
    a_directory = tmp_path

    with pytest.raises(GuessLogWriteError):
        GuessLog(a_directory, SESSION_START).append(1, RED_SEVEN_MISSED)
