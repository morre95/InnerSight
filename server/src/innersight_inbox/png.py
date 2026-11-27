"""Read the size of a PNG picture from its first bytes, without decoding the picture."""

import struct

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# After the signature comes the header chunk: its length, its name, then width and height.
_HEADER_NAME = b"IHDR"
_SIZE_START = len(_SIGNATURE) + 8
_SIZE_END = _SIZE_START + 8


def read_png_size(content: bytes) -> tuple[int, int] | None:
    """The width and height the picture says it has, or None if the bytes are not a PNG."""
    is_png = content.startswith(_SIGNATURE) and content[12:16] == _HEADER_NAME
    if not is_png or len(content) < _SIZE_END:
        return None
    width, height = struct.unpack(">II", content[_SIZE_START:_SIZE_END])
    return width, height
