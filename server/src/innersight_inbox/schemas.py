"""What an example looks like on the wire. The field names are a contract with the app and
with 'innersight pull'; contract/example.json is the sample that all three are tested against.
"""

from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# A rank or a color as the app names it, such as "7", "+2", "reverse" or "red". The inbox does
# not know the ranks; 'innersight pull' checks them against the ones the detector has.
CardWord = Annotated[str, StringConstraints(pattern=r"^[a-z0-9+]{1,24}$")]
MAX_FRAME_SIDE = 8192


class BoxSchema(BaseModel):
    """Pixel rectangle in the frame: (x1, y1) is the top-left corner."""

    model_config = ConfigDict(extra="forbid")

    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(gt=0)
    y2: int = Field(gt=0)


class ExampleMetadata(BaseModel):
    """What the app tells about an uploaded frame."""

    model_config = ConfigDict(extra="forbid")

    rank: CardWord = Field(description="The rank of the true card, as set by the player")
    color: CardWord = Field(description="The color of the true card, as set by the player")
    box: BoxSchema = Field(description="Where the detector found the card in the frame")
    frame_width: int = Field(gt=0, le=MAX_FRAME_SIDE)
    frame_height: int = Field(gt=0, le=MAX_FRAME_SIDE)
    read_rank: CardWord = Field(description="The rank the detector read")
    read_color: CardWord = Field(description="The color that was read")
    confidence: float = Field(ge=0, le=1, description="How sure the detector was of the rank")

    @model_validator(mode="after")
    def _box_must_be_inside_the_frame(self) -> Self:
        box = self.box
        is_inside = box.x1 < box.x2 <= self.frame_width and box.y1 < box.y2 <= self.frame_height
        if not is_inside:
            raise ValueError("the box must have a size and lie inside the frame")
        return self


class StoredExample(ExampleMetadata):
    """An example in the inbox: what the app told, and what the inbox added."""

    id: str
    created_at: datetime
