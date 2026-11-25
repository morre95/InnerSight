"""Keep a log of every guessing round: the card the model read and how sure it was."""

import csv
from datetime import datetime
from pathlib import Path

from innersight.errors import GuessLogWriteError
from innersight.guessing import GuessRound

COLUMNS = ("session", "card_number", "card", "confidence", "outcome")


class GuessLog:
    """A CSV file with one row for every round, from every session played."""

    def __init__(self, file: Path, session_start: datetime) -> None:
        self._file = file
        self._session = session_start.isoformat(timespec="seconds")

    def append(self, card_number: int, played_round: GuessRound) -> None:
        """Add the round to the file at once, so a session that is cut short keeps its rounds."""
        row = (
            self._session,
            card_number,
            played_round.face.label,
            f"{played_round.confidence:.3f}",
            played_round.outcome,
        )
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            is_new_file = not self._file.exists()
            with self._file.open("a", newline="") as log_file:
                writer = csv.writer(log_file)
                if is_new_file:
                    writer.writerow(COLUMNS)
                writer.writerow(row)
        except OSError as error:
            raise GuessLogWriteError(f"Could not write {self._file}: {error}") from error
