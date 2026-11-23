"""Speak short phrases through the speakers with Pocket TTS."""

import numpy as np
import sounddevice
from pocket_tts import TTSModel

from innersight.errors import SpeechError

VOICE = "alba"


class PocketTtsVoice:
    """Speaks phrases in one voice and keeps every generated phrase for reuse.

    Generating a phrase takes a few tenths of a second on a CPU; saying it again is instant.
    """

    def __init__(self) -> None:
        self._model = TTSModel.load_model()
        self._voice_state = self._model.get_state_for_audio_prompt(VOICE)
        self._clips: dict[str, np.ndarray] = {}

    def say(self, phrase: str) -> None:
        """Start speaking the phrase and return at once, cutting off a phrase still playing."""
        if phrase not in self._clips:
            self._clips[phrase] = self._model.generate_audio(self._voice_state, phrase).numpy()
        try:
            sounddevice.play(self._clips[phrase], self._model.sample_rate)
        except sounddevice.PortAudioError as error:
            raise SpeechError(f"Could not play audio: {error}") from error
