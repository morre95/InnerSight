# InnerSight for Android and web

The Flutter app recognizes UNO cards and runs the guessing game on Android and
in the browser. Card recognition runs on the device, and camera frames stay
there, with one exception that is off unless you turn it on: with "Collect
misread cards" under Advanced, the frame of a round you choose on the result
board is sent to the server whose address you entered. The app stores no
pictures itself. The app downloads the model and loads ONNX Runtime Web from
jsDelivr.

## Run in a browser

From the repository root, export the model if `mobile/assets/models/own-cards.onnx`
is missing. This step requires the trained weights.

```sh
uv run --group export python scripts/export_mobile_model.py --weights weights/own-cards.pt
cd mobile
flutter run -d chrome
```

Camera access requires browser permission and a secure context such as HTTPS
or localhost. The game prefers the front camera when the browser identifies it.
The web app plays bundled voice clips. If the spoken phrases change, regenerate
the clips from the repository root with `uv run python scripts/export_web_speech.py`.
The export uses Pocket TTS and requires `ffmpeg`.

## Build for GitHub Pages

Run this from `mobile/`. Use the repository name and its exact casing in the
base path. For a site served at a domain root, use `/` instead.

```sh
flutter build web --base-href /InnerSight/ --no-web-resources-cdn
```

GitHub Pages serves the root of the `gh-pages` branch. To publish an update,
commit the contents of `build/web/` to that branch and keep the `.nojekyll`
file at its root. [Live site](https://morre95.github.io/InnerSight/)

The build requires the ONNX model, which is ignored by Git in the app source.
The published site serves the model as a downloadable asset.
