from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from samples import CONTRACT_JSON, CONTRACT_PNG, contract_with, make_png

from innersight_inbox.app import create_app, create_app_from_environment
from innersight_inbox.settings import Settings
from innersight_inbox.store import ExampleStore

UPLOAD_TOKEN = "u" * 32
PULL_TOKEN = "p" * 32
UPLOAD = {"Authorization": f"Bearer {UPLOAD_TOKEN}"}
PULL = {"Authorization": f"Bearer {PULL_TOKEN}"}
WEB_APP = "https://app.example"
EXAMPLES = "/api/v1/examples"
UNKNOWN_ID = "20261127T205301000000-0123abcd"
MAX_IMAGE_BYTES = 64 * 1024


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        upload_token=UPLOAD_TOKEN,
        pull_token=PULL_TOKEN,
        data_dir=tmp_path,
        allowed_origins=WEB_APP,
        max_examples=2,
        max_image_bytes=MAX_IMAGE_BYTES,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), raise_server_exceptions=False)


def upload(
    client: TestClient,
    image: bytes = CONTRACT_PNG,
    metadata: str = CONTRACT_JSON,
    headers: dict[str, str] = UPLOAD,
) -> Response:
    return client.post(
        EXAMPLES,
        files={"image": ("frame.png", image, "image/png")},
        data={"metadata": metadata},
        headers=headers,
    )


def error_code(response: Response) -> str:
    body = response.json()
    assert body["success"] is False
    return body["error"]["code"]


def test_stores_an_uploaded_example_and_lists_it(client: TestClient) -> None:
    uploaded = upload(client)

    listed = client.get(EXAMPLES, headers=PULL).json()

    assert uploaded.status_code == 201
    assert listed["data"] == [uploaded.json()["data"]]
    assert listed["data"][0]["rank"] == "9"


def test_gives_back_the_picture_as_it_was_uploaded(client: TestClient) -> None:
    example_id = upload(client).json()["data"]["id"]

    picture = client.get(f"{EXAMPLES}/{example_id}/image", headers=PULL)

    assert picture.content == CONTRACT_PNG
    assert picture.headers["content-type"] == "image/png"


def test_lists_a_page_at_a_time_and_tells_where_the_next_one_starts(client: TestClient) -> None:
    first_id, second_id = (upload(client).json()["data"]["id"] for _ in range(2))

    first_page = client.get(EXAMPLES, params={"limit": 1}, headers=PULL).json()
    second_page = client.get(EXAMPLES, params={"limit": 1, "after": first_id}, headers=PULL).json()

    assert [example["id"] for example in first_page["data"]] == [first_id]
    assert first_page["meta"]["pagination"] == {"has_more": True, "next_after": first_id}
    assert [example["id"] for example in second_page["data"]] == [second_id]
    assert second_page["meta"]["pagination"] == {"has_more": False, "next_after": None}


def test_removes_a_deleted_example(client: TestClient) -> None:
    example_id = upload(client).json()["data"]["id"]

    deleted = client.delete(f"{EXAMPLES}/{example_id}", headers=PULL)

    assert deleted.status_code == 204
    assert client.get(EXAMPLES, headers=PULL).json()["data"] == []


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer " + "x" * 32}])
def test_refuses_an_upload_without_a_valid_token(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = upload(client, headers=headers)

    assert response.status_code == 401
    assert error_code(response) == "UNAUTHORIZED"


def test_refuses_the_pull_token_for_uploading(client: TestClient) -> None:
    response = upload(client, headers=PULL)

    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", EXAMPLES),
        ("GET", f"{EXAMPLES}/{UNKNOWN_ID}/image"),
        ("DELETE", f"{EXAMPLES}/{UNKNOWN_ID}"),
    ],
)
def test_refuses_the_upload_token_for_reading_and_removing(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path, headers=UPLOAD)

    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_refuses_a_file_that_is_not_a_png(client: TestClient) -> None:
    response = upload(client, image=b"\xff\xd8\xff a jpeg, or anything else")

    assert response.status_code == 400
    assert error_code(response) == "INVALID_UPLOAD"


def test_refuses_a_picture_of_another_size_than_the_metadata_tells(client: TestClient) -> None:
    response = upload(client, image=make_png(100, 100))

    assert response.status_code == 400
    assert error_code(response) == "INVALID_UPLOAD"


def test_refuses_a_box_outside_the_frame_and_names_the_field(client: TestClient) -> None:
    box = {"x1": 0, "y1": 0, "x2": 9999, "y2": 10}

    response = upload(client, metadata=contract_with(box=box))

    assert response.status_code == 400
    assert "metadata" in response.json()["error"]["message"]


def test_refuses_a_picture_above_the_size_limit(client: TestClient) -> None:
    response = upload(client, image=bytes(MAX_IMAGE_BYTES * 2))

    # The framework stops reading and answers this itself, so there is no envelope.
    assert response.status_code == 413


def test_refuses_an_upload_when_the_inbox_is_full(client: TestClient) -> None:
    upload(client)
    upload(client)

    response = upload(client)

    assert response.status_code == 507
    assert error_code(response) == "INBOX_FULL"


def test_knows_no_example_under_an_id_it_did_not_give_out(client: TestClient) -> None:
    response = client.delete(f"{EXAMPLES}/{UNKNOWN_ID}", headers=PULL)

    assert response.status_code == 404
    assert error_code(response) == "EXAMPLE_NOT_FOUND"


def test_refuses_an_id_that_does_not_look_like_one_of_its_own(
    client: TestClient, tmp_path: Path
) -> None:
    outside_file = tmp_path.parent / "outside.json"
    outside_file.write_text("{}")

    response = client.delete(f"{EXAMPLES}/..%2Foutside", headers=PULL)

    assert response.status_code in (400, 404)
    assert response.json()["success"] is False
    assert outside_file.is_file()


def test_refuses_a_page_size_above_the_limit(client: TestClient) -> None:
    response = client.get(EXAMPLES, params={"limit": 1000}, headers=PULL)

    assert response.status_code == 400
    assert error_code(response) == "INVALID_REQUEST"
    assert "limit" in response.json()["error"]["message"]


def test_answers_a_path_that_does_not_exist_in_the_same_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert error_code(response) == "NOT_FOUND"


def test_answers_a_failure_of_its_own_without_telling_what_went_wrong(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(self: ExampleStore, after: str | None, limit: int) -> None:
        raise RuntimeError("the disk at /srv/secret is gone")

    monkeypatch.setattr(ExampleStore, "list_examples", fail)

    response = client.get(EXAMPLES, headers=PULL)

    assert response.status_code == 500
    assert error_code(response) == "INTERNAL_ERROR"
    assert "secret" not in response.text


def preflight(client: TestClient, origin: str, method: str) -> Response:
    return client.options(
        EXAMPLES,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization",
        },
    )


def test_lets_the_web_app_upload_from_a_browser(client: TestClient) -> None:
    response = preflight(client, WEB_APP, "POST")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == WEB_APP


def test_lets_no_other_web_page_upload_from_a_browser(client: TestClient) -> None:
    response = preflight(client, "https://elsewhere.example", "POST")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_lets_no_web_page_read_the_examples_from_a_browser(client: TestClient) -> None:
    response = preflight(client, WEB_APP, "GET")

    assert response.status_code == 400


def test_does_not_describe_its_api_to_visitors(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_tells_that_it_is_running_without_a_token(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"success": True}


def test_does_not_start_without_its_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INBOX_UPLOAD_TOKEN", raising=False)

    with pytest.raises(ValueError):
        create_app_from_environment()
