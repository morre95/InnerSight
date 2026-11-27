"""Let a request through only with the token that its kind of work needs."""

import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr

from innersight_inbox.errors import InvalidToken, TokenNotAllowed
from innersight_inbox.settings import Settings

_bearer = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _is_token(given: str, token: SecretStr) -> bool:
    # Compared in a time that does not tell how much of the token was right.
    return secrets.compare_digest(given.encode(), token.get_secret_value().encode())


def _require(
    wanted: Callable[[Settings], SecretStr], other: Callable[[Settings], SecretStr]
) -> Callable[[Request, Credentials], None]:
    def check(request: Request, credentials: Credentials) -> None:
        settings: Settings = request.app.state.settings
        if credentials is None:
            raise InvalidToken("This needs a token, sent as 'Authorization: Bearer <token>'")
        if _is_token(credentials.credentials, wanted(settings)):
            return
        if _is_token(credentials.credentials, other(settings)):
            raise TokenNotAllowed("This token is for other work than this")
        raise InvalidToken("The token is not valid")

    return check


require_upload_token = _require(lambda s: s.upload_token, lambda s: s.pull_token)
require_pull_token = _require(lambda s: s.pull_token, lambda s: s.upload_token)
