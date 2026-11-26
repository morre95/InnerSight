"""Generate the browser's announcement clips using the desktop game's voice."""

import json
import subprocess
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from pocket_tts import TTSModel

from innersight.announcement import TOO_CLOSE_PHRASE, spoken_name
from innersight.cards import CARD_BACK, DECK
from innersight.guessing import (
    CORRECTION_PHRASE,
    FIRST_CARD_PHRASE,
    LAST_CARD_PHRASE,
    NEXT_CARD_PHRASE,
    NO_ANSWER_PHRASE,
    NO_CARD_PHRASE,
    SESSION_FINISHED_PHRASE,
    GuessOutcome,
)
from innersight.speech import VOICE

OUTPUT = Path(__file__).resolve().parents[1] / "mobile" / "web" / "speech"
# Matches the maximum session size on the Flutter home screen.
MAX_CARD_COUNT = 50


def phrases() -> list[str]:
    prompts = (
        FIRST_CARD_PHRASE,
        LAST_CARD_PHRASE,
        NEXT_CARD_PHRASE,
        NO_ANSWER_PHRASE,
        NO_CARD_PHRASE,
        CORRECTION_PHRASE,
        TOO_CLOSE_PHRASE,
        SESSION_FINISHED_PHRASE,
    )
    return sorted(
        {part.strip().lower() for prompt in prompts for part in prompt.split(".")}
        | {spoken_name(card).lower() for card in (*DECK, CARD_BACK)}
        | {outcome.value for outcome in GuessOutcome}
        | {str(count) for count in range(MAX_CARD_COUNT + 1)}
    )


def main() -> None:
    model = TTSModel.load_model()
    voice = model.get_state_for_audio_prompt(VOICE)
    sample_rate = model.sample_rate
    silence = bytes(round(sample_rate * 0.06) * 2)
    index = {}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        wave_path = Path(tmp) / "clips.wav"
        with wave.open(str(wave_path), "wb") as wav:
            wav.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
            for phrase in phrases():
                start = wav.tell()
                samples = model.generate_audio(voice, f"{phrase.capitalize()}.").numpy()
                pcm = np.rint(samples.clip(-1, 1) * 32767).astype("<i2")
                wav.writeframesraw(pcm.tobytes())
                index[phrase] = [round(start / sample_rate, 6), round(len(pcm) / sample_rate, 6)]
                wav.writeframesraw(silence)

        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", wave_path, "-b:a", "48k", "clips.mp3"],
            cwd=OUTPUT,
            check=True,
        )
    (OUTPUT / "clips.json").write_text(json.dumps(index, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
