import pytest
from pydantic import ValidationError
from samples import CONTRACT_JSON, contract_with

from innersight_inbox.schemas import ExampleMetadata


def test_accepts_the_example_in_the_shared_contract_file() -> None:
    metadata = ExampleMetadata.model_validate_json(CONTRACT_JSON)

    assert (metadata.rank, metadata.color, metadata.read_rank) == ("9", "red", "6")


@pytest.mark.parametrize(
    "box",
    [
        {"x1": 120, "y1": 200, "x2": 481, "y2": 560},
        {"x1": 120, "y1": 200, "x2": 360, "y2": 721},
        {"x1": 360, "y1": 200, "x2": 360, "y2": 560},
    ],
)
def test_refuses_a_box_that_is_empty_or_reaches_outside_the_frame(box: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        ExampleMetadata.model_validate_json(contract_with(box=box))


@pytest.mark.parametrize("rank", ["", "../etc", "Seven", "a" * 25])
def test_refuses_a_rank_that_is_not_a_short_plain_word(rank: str) -> None:
    with pytest.raises(ValidationError):
        ExampleMetadata.model_validate_json(contract_with(rank=rank))


def test_refuses_a_field_it_does_not_know() -> None:
    with pytest.raises(ValidationError):
        ExampleMetadata.model_validate_json(contract_with(note="hello"))
