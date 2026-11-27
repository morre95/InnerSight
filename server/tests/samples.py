"""Sample uploads shared by the tests."""

import json
import struct
import zlib
from pathlib import Path

from innersight_inbox.schemas import ExampleMetadata

CONTRACT_FILE = Path(__file__).parent.parent / "contract" / "example.json"
CONTRACT_JSON = CONTRACT_FILE.read_text()
CONTRACT_METADATA = ExampleMetadata.model_validate_json(CONTRACT_JSON)


def contract_with(**changes: object) -> str:
    """The contract sample as JSON, with some of its fields changed."""
    return json.dumps({**json.loads(CONTRACT_JSON), **changes})


def make_png(width: int, height: int) -> bytes:
    """A black PNG picture of the given size."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    rows = b"".join(b"\x00" + bytes(width) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


CONTRACT_PNG = make_png(CONTRACT_METADATA.frame_width, CONTRACT_METADATA.frame_height)
