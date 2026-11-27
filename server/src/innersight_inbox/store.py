"""Keep the uploaded examples as files: one picture and one metadata file for each."""

import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

from innersight_inbox.errors import ExampleNotFound, InboxFull
from innersight_inbox.schemas import ExampleMetadata, StoredExample

# An id starts with the time it was given, so the ids sort in the order of the uploads. The
# store gives the ids itself and takes no other, so no id can point outside its directory.
ID_PATTERN = r"^\d{8}T\d{12}-[0-9a-f]{8}$"
_ID_FORMAT = re.compile(ID_PATTERN)
_IMAGE_SUFFIX = ".png"
_METADATA_SUFFIX = ".json"
_UNFINISHED_SUFFIX = ".part"


class ExampleStore:
    """A directory of examples.

    An example is there once its metadata file is. That file is written last and removed
    first, so a picture without metadata is an upload that did not finish, and is not listed.
    """

    def __init__(self, directory: Path, max_examples: int) -> None:
        self._directory = directory
        self._max_examples = max_examples

    def add(self, image: bytes, metadata: ExampleMetadata) -> StoredExample:
        """Store the picture with its metadata under a new id."""
        self._directory.mkdir(parents=True, exist_ok=True)
        if len(self._metadata_files()) >= self._max_examples:
            raise InboxFull(f"The inbox holds {self._max_examples} examples and takes no more")
        now = datetime.now(UTC)
        example = StoredExample(
            id=f"{now:%Y%m%dT%H%M%S%f}-{secrets.token_hex(4)}",
            created_at=now,
            **metadata.model_dump(),
        )
        _write_whole(self._file(example.id, _IMAGE_SUFFIX), image)
        _write_whole(self._file(example.id, _METADATA_SUFFIX), example.model_dump_json().encode())
        return example

    def list_examples(self, after: str | None, limit: int) -> list[StoredExample]:
        """Up to `limit` examples in the order they were uploaded, from the one after `after`."""
        ids = sorted(metadata_file.stem for metadata_file in self._metadata_files())
        wanted_ids = [example_id for example_id in ids if after is None or example_id > after]
        return [self._read(example_id) for example_id in wanted_ids[:limit]]

    def image_path(self, example_id: str) -> Path:
        self._require(example_id)
        return self._file(example_id, _IMAGE_SUFFIX)

    def delete(self, example_id: str) -> None:
        self._require(example_id)
        self._file(example_id, _METADATA_SUFFIX).unlink()
        self._file(example_id, _IMAGE_SUFFIX).unlink(missing_ok=True)

    def _require(self, example_id: str) -> None:
        is_known = _ID_FORMAT.fullmatch(example_id) is not None and (
            self._file(example_id, _METADATA_SUFFIX).is_file()
        )
        if not is_known:
            raise ExampleNotFound(f"There is no example {example_id!r} in the inbox")

    def _read(self, example_id: str) -> StoredExample:
        metadata_file = self._file(example_id, _METADATA_SUFFIX)
        return StoredExample.model_validate_json(metadata_file.read_bytes())

    def _metadata_files(self) -> list[Path]:
        return list(self._directory.glob(f"*{_METADATA_SUFFIX}"))

    def _file(self, example_id: str, suffix: str) -> Path:
        return self._directory / f"{example_id}{suffix}"


def _write_whole(file: Path, content: bytes) -> None:
    """Write the file so that it is either there with all its content, or not there."""
    unfinished_file = file.with_name(file.name + _UNFINISHED_SUFFIX)
    unfinished_file.write_bytes(content)
    unfinished_file.replace(file)
