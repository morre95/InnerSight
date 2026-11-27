from pathlib import Path

import pytest
from samples import CONTRACT_METADATA, CONTRACT_PNG

from innersight_inbox.errors import ExampleNotFound, InboxFull
from innersight_inbox.store import ExampleStore


@pytest.fixture
def store(tmp_path: Path) -> ExampleStore:
    return ExampleStore(tmp_path, max_examples=3)


def test_lists_an_added_example_with_what_the_app_told_about_it(store: ExampleStore) -> None:
    added = store.add(CONTRACT_PNG, CONTRACT_METADATA)

    assert store.list_examples(after=None, limit=10) == [added]
    assert added.rank == CONTRACT_METADATA.rank


def test_keeps_the_picture_of_an_example(store: ExampleStore) -> None:
    added = store.add(CONTRACT_PNG, CONTRACT_METADATA)

    assert store.image_path(added.id).read_bytes() == CONTRACT_PNG


def test_lists_the_examples_in_the_order_they_were_added(store: ExampleStore) -> None:
    added = [store.add(CONTRACT_PNG, CONTRACT_METADATA) for _ in range(3)]

    assert store.list_examples(after=None, limit=10) == added


def test_lists_no_more_examples_than_asked_for(store: ExampleStore) -> None:
    first, _, _ = (store.add(CONTRACT_PNG, CONTRACT_METADATA) for _ in range(3))

    assert store.list_examples(after=None, limit=1) == [first]


def test_goes_on_after_the_example_it_is_told(store: ExampleStore) -> None:
    first, second, third = (store.add(CONTRACT_PNG, CONTRACT_METADATA) for _ in range(3))

    assert store.list_examples(after=first.id, limit=10) == [second, third]


def test_does_not_list_an_example_whose_upload_is_not_finished(
    store: ExampleStore, tmp_path: Path
) -> None:
    (tmp_path / "20261127T205301000000-0123abcd.png").write_bytes(CONTRACT_PNG)

    assert store.list_examples(after=None, limit=10) == []


def test_lists_nothing_before_the_first_upload(tmp_path: Path) -> None:
    store = ExampleStore(tmp_path / "not-made-yet", max_examples=3)

    assert store.list_examples(after=None, limit=10) == []


def test_removes_a_deleted_example_and_its_picture(store: ExampleStore, tmp_path: Path) -> None:
    added = store.add(CONTRACT_PNG, CONTRACT_METADATA)

    store.delete(added.id)

    assert list(tmp_path.iterdir()) == []


def test_takes_no_more_examples_when_it_is_full(store: ExampleStore) -> None:
    for _ in range(3):
        store.add(CONTRACT_PNG, CONTRACT_METADATA)

    with pytest.raises(InboxFull):
        store.add(CONTRACT_PNG, CONTRACT_METADATA)


def test_takes_examples_again_once_one_is_deleted(store: ExampleStore) -> None:
    added = [store.add(CONTRACT_PNG, CONTRACT_METADATA) for _ in range(3)]

    store.delete(added[0].id)

    store.add(CONTRACT_PNG, CONTRACT_METADATA)


@pytest.mark.parametrize("example_id", ["20261127T205301000000-0123abcd", "../secrets", ""])
def test_knows_no_example_under_an_id_it_did_not_give_out(
    store: ExampleStore, example_id: str
) -> None:
    with pytest.raises(ExampleNotFound):
        store.image_path(example_id)


def test_does_not_delete_a_file_outside_its_directory(tmp_path: Path) -> None:
    store = ExampleStore(tmp_path / "inbox", max_examples=3)
    store.add(CONTRACT_PNG, CONTRACT_METADATA)
    outside_file = tmp_path / "outside.json"
    outside_file.write_text("{}")

    with pytest.raises(ExampleNotFound):
        store.delete("../outside")

    assert outside_file.is_file()
