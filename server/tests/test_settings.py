from pathlib import Path

import pytest
from pydantic import ValidationError

from innersight_inbox.settings import MIN_TOKEN_LENGTH, Settings

UPLOAD_TOKEN = "u" * MIN_TOKEN_LENGTH
PULL_TOKEN = "p" * MIN_TOKEN_LENGTH


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    monkeypatch.setenv("INBOX_UPLOAD_TOKEN", UPLOAD_TOKEN)
    monkeypatch.setenv("INBOX_PULL_TOKEN", PULL_TOKEN)
    monkeypatch.setenv("INBOX_DATA_DIR", str(tmp_path))
    return monkeypatch


def test_reads_the_tokens_and_the_directory_from_the_environment(
    environment: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = Settings()

    assert settings.upload_token.get_secret_value() == UPLOAD_TOKEN
    assert settings.data_dir == tmp_path


@pytest.mark.parametrize("missing", ["INBOX_UPLOAD_TOKEN", "INBOX_PULL_TOKEN", "INBOX_DATA_DIR"])
def test_does_not_start_without_both_tokens_and_a_directory(
    environment: pytest.MonkeyPatch, missing: str
) -> None:
    environment.delenv(missing)

    with pytest.raises(ValidationError):
        Settings()


def test_does_not_start_with_a_token_short_enough_to_guess(
    environment: pytest.MonkeyPatch,
) -> None:
    environment.setenv("INBOX_PULL_TOKEN", "p" * (MIN_TOKEN_LENGTH - 1))

    with pytest.raises(ValidationError):
        Settings()


def test_does_not_show_a_token_that_it_refuses(environment: pytest.MonkeyPatch) -> None:
    environment.setenv("INBOX_PULL_TOKEN", "too-short-a-secret")

    with pytest.raises(ValidationError) as failure:
        Settings()

    assert "too-short-a-secret" not in str(failure.value)


def test_does_not_start_with_the_same_token_for_uploading_and_pulling(
    environment: pytest.MonkeyPatch,
) -> None:
    environment.setenv("INBOX_PULL_TOKEN", UPLOAD_TOKEN)

    with pytest.raises(ValidationError):
        Settings()


def test_does_not_show_a_token_when_the_settings_are_printed(
    environment: pytest.MonkeyPatch,
) -> None:
    assert UPLOAD_TOKEN not in repr(Settings())


def test_splits_the_allowed_origins_at_the_commas(environment: pytest.MonkeyPatch) -> None:
    environment.setenv("INBOX_ALLOWED_ORIGINS", "https://a.example, https://b.example")

    assert Settings().origins == ["https://a.example", "https://b.example"]
