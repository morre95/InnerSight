# InnerSight inbox

A small server that receives the training examples collected in games in the InnerSight app,
and keeps them until `innersight pull` fetches them to the computer that trains the detector.
The app itself stores no pictures.

It is a project of its own, apart from the `innersight` package, so the server needs FastAPI
and nothing of the detector.

```bash
uv sync
uv run pytest
```

`contract/example.json` is the sample of what the app tells about an example. The inbox, the
app and `innersight pull` are each tested against it, so the field names cannot drift apart.
