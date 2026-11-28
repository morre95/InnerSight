# InnerSight inbox

A small server that receives the training examples collected in games in the InnerSight app,
and keeps them until `innersight pull` fetches them to the computer that trains the detector.
The app itself stores no pictures.

It is a project of its own, apart from the `innersight` package, so the server needs FastAPI
and nothing of the detector.

## Run it on a server

You need a server with Docker and a domain name that points at it. The web app is served over
HTTPS and a browser lets such a page talk to HTTPS only, so the inbox needs a certificate;
Caddy gets one for the domain by itself.

```bash
cp .env.example .env      # then fill in the domain and two secrets, as the file tells
docker compose up -d --build
curl https://inbox.example.com/healthz
```

Ports 80 and 443 must be open. The examples are kept in the `inbox-data` volume.

### On a server that already runs nginx

Caddy cannot have ports 80 and 443 there. Start the inbox alone, open to the server itself
only on port 8010, and let nginx pass the requests on:

```bash
docker compose -f compose.yaml -f compose.nginx.yaml up -d --build inbox
cp nginx/inbox.conf /etc/nginx/sites-available/innersight-inbox   # then put in the domain
ln -s /etc/nginx/sites-available/innersight-inbox /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d inbox.example.com
```

`INBOX_DOMAIN` must still be set in `.env`, though only Caddy reads it.

In the app, under Advanced, turn on collecting and enter `https://inbox.example.com` and the
upload token. On the computer that trains, fetch the examples with the pull token:

```bash
INNERSIGHT_PULL_TOKEN=... uv run innersight pull --server https://inbox.example.com
```

## Settings

| Variable                | Meaning                                                           |
| ----------------------- | ----------------------------------------------------------------- |
| `INBOX_UPLOAD_TOKEN`    | Lets the app add examples. At least 32 characters.                |
| `INBOX_PULL_TOKEN`      | Lets `innersight pull` list, read and remove examples.            |
| `INBOX_DATA_DIR`        | Where the examples are kept. The image sets it to `/data`.        |
| `INBOX_ALLOWED_ORIGINS` | The web pages that may upload from a browser, separated by commas |
| `INBOX_MAX_EXAMPLES`    | How many examples the inbox holds before it refuses more (2000)   |
| `INBOX_MAX_IMAGE_BYTES` | The largest picture it takes (5 MB)                               |

The inbox does not start without both tokens, with a token shorter than 32 characters, or with
the same token for both kinds of work.

## API

Every request but the health check needs `Authorization: Bearer <token>`.

| Request                              | Token  | Answer                                      |
| ------------------------------------ | ------ | ------------------------------------------- |
| `POST /api/v1/examples`              | upload | 201 and the stored example                  |
| `GET /api/v1/examples?after=&limit=` | pull   | A page of examples, oldest first            |
| `GET /api/v1/examples/{id}/image`    | pull   | The picture, as it was uploaded             |
| `DELETE /api/v1/examples/{id}`       | pull   | 204                                         |
| `GET /healthz`                       | none   | 200 when the inbox is running               |

An upload is a multipart form with two parts: `image`, the whole camera frame as a PNG, and
`metadata`, a JSON object like `contract/example.json`. That file is the sample of what the app
tells about an example. The inbox, the app and `innersight pull` are each tested against it, so
the field names cannot drift apart.

A listing takes `limit` (20 if left out, 100 at most) and `after`, the id of the last example
of the page before. Its `meta.pagination` tells whether there are more.

An answer is `{"success": true, "data": ...}`, or
`{"success": false, "error": {"code": "...", "message": "..."}}` with one of these codes:

| Status | Code                | When                                                       |
| ------ | ------------------- | ---------------------------------------------------------- |
| 400    | `INVALID_UPLOAD`    | The picture is not a PNG of the size told, or a field is wrong |
| 400    | `INVALID_REQUEST`   | A query value or an id is not as it should be              |
| 401    | `UNAUTHORIZED`      | The token is missing or not valid                          |
| 403    | `FORBIDDEN`         | The token is the one for the other kind of work            |
| 404    | `EXAMPLE_NOT_FOUND` | There is no example with that id                           |
| 507    | `INBOX_FULL`        | The inbox holds as many examples as it may                 |
| 500    | `INTERNAL_ERROR`    | The inbox failed; the cause is in its log, not in the answer |

A request that is too large is answered with a plain 413 and no such body, as it is stopped
before the inbox reads it: by Caddy or nginx above 6 MB, and by the framework above the picture
limit.

## What keeps the pictures safe

- The token in the app can only add examples. A token that leaks from a phone or a browser
  cannot read the pictures that are already there. `innersight pull` shows every example for a
  check before it is saved, so a leaked upload token cannot put pictures into the training set
  unseen either.
- The tokens are long random secrets, so they cannot be found by trying. There is no limit on
  the number of tries.
- The inbox gives the ids itself and takes no other, so no request can reach a file outside
  its directory.
- `innersight pull` removes each example from the server once it is saved or discarded, so
  pictures of your room do not stay on the server longer than needed.
- In the container the inbox runs as a user without rights, and can write to its data only.

## Develop

```bash
uv sync
uv run pytest
uv run uvicorn innersight_inbox.app:create_app_from_environment --factory --reload
```

The last command needs the three required settings in the environment. Lint and format from
the repository root, whose ruff settings cover this project too.
