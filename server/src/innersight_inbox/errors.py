"""The failures the inbox answers a request with. Each has an HTTP status and a code."""


class InboxError(Exception):
    """A failure that is told to the client, with a code that a program can act on."""

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidToken(InboxError):
    status_code = 401
    code = "UNAUTHORIZED"


class TokenNotAllowed(InboxError):
    status_code = 403
    code = "FORBIDDEN"


class InvalidUpload(InboxError):
    status_code = 400
    code = "INVALID_UPLOAD"


class ExampleNotFound(InboxError):
    status_code = 404
    code = "EXAMPLE_NOT_FOUND"


class InboxFull(InboxError):
    status_code = 507
    code = "INBOX_FULL"
