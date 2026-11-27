"""The configuration of the inbox, read from the environment."""

from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# A token of this length from a random source cannot be guessed by trying.
MIN_TOKEN_LENGTH = 32
DEFAULT_MAX_EXAMPLES = 2000
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024


class Settings(BaseSettings):
    """Read from variables that start with INBOX_. Creating it fails when one is missing.

    There are two tokens, so that the one kept in the app can add examples and do nothing
    else. Only the pull token, kept on the computer that trains, can read and remove them.
    """

    model_config = SettingsConfigDict(env_prefix="INBOX_")

    upload_token: SecretStr = Field(min_length=MIN_TOKEN_LENGTH)
    pull_token: SecretStr = Field(min_length=MIN_TOKEN_LENGTH)
    data_dir: Path
    # The web pages that may upload from a browser, separated by commas.
    allowed_origins: str = ""
    max_examples: int = Field(default=DEFAULT_MAX_EXAMPLES, gt=0)
    max_image_bytes: int = Field(default=DEFAULT_MAX_IMAGE_BYTES, gt=0)

    @model_validator(mode="after")
    def _tokens_must_differ(self) -> Self:
        if self.upload_token.get_secret_value() == self.pull_token.get_secret_value():
            raise ValueError("the upload token and the pull token must not be the same")
        return self

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
