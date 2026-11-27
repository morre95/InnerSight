globalThis.innerSightSpeech = (() => {
  let context;
  let loading;
  let announcement = 0;
  const playing = new Set();

  function enable() {
    try {
      const Audio = globalThis.AudioContext || globalThis.webkitAudioContext;
      context ??= new Audio();
      if (context.state !== 'running') {
        context.resume().catch(error => console.warn('Could not enable audio:', error));
      }
    } catch (error) {
      console.warn('Could not enable audio:', error);
    }
  }

  async function fetchClipAsset(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Speech asset returned HTTP ${response.status}`);
    return response;
  }

  async function load() {
    const [index, audio] = await Promise.all([
      fetchClipAsset('speech/clips.json').then(response => response.json()),
      fetchClipAsset('speech/clips.mp3').then(response => response.arrayBuffer()),
    ]);
    return { index, buffer: await context.decodeAudioData(audio) };
  }

  function stop() {
    announcement += 1;
    for (const source of playing) source.stop();
    playing.clear();
    const voice = globalThis.speechSynthesis;
    if (voice?.speaking || voice?.pending) voice.cancel();
  }

  function speakWithBrowserVoice(phrase) {
    if (!globalThis.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(phrase);
    utterance.lang = 'en-US';
    speechSynthesis.speak(utterance);
  }

  function clipKeys(phrase, index) {
    return phrase.toLowerCase().split(/[.,]/).map(part => part.trim())
      .filter(Boolean).flatMap(part => {
        if (Object.hasOwn(index, part)) return [part];
        // The final score includes a spoken outcome followed by its count.
        const count = part.match(/^(.+) (\d+)$/);
        return count ? [count[1], count[2]] : [part];
      });
  }

  async function say(phrase) {
    stop();
    const requested = announcement;
    if (!context) {
      speakWithBrowserVoice(phrase);
      return;
    }

    try {
      loading ??= load().catch(error => {
        loading = undefined;
        throw error;
      });
      const { index, buffer } = await loading;
      if (requested !== announcement) return;
      const keys = clipKeys(phrase, index);
      if (keys.some(key => !Object.hasOwn(index, key))) {
        speakWithBrowserVoice(phrase);
        return;
      }

      let when = context.currentTime + 0.015;
      for (const key of keys) {
        const [offset, duration] = index[key];
        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        source.onended = () => {
          playing.delete(source);
          source.disconnect();
        };
        source.start(when, offset, duration);
        playing.add(source);
        when += duration + 0.06;
      }
    } catch (error) {
      if (requested !== announcement) return;
      console.warn('Could not play bundled speech:', error);
      stop();
      speakWithBrowserVoice(phrase);
    }
  }

  return { enable, say, stop };
})();
