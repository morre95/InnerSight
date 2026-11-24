import 'package:flutter_tts/flutter_tts.dart';

/// Speaks recognized UNO card phrases via Android's native TTS engine.
class TtsSpeaker {
  TtsSpeaker({FlutterTts? tts, this.isMuted = false}) : _tts = tts ?? FlutterTts();

  final FlutterTts _tts;
  bool isMuted;
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;
    await _tts.setLanguage('en-US');
    await _tts.setVolume(1.0);
    await _tts.awaitSpeakCompletion(false);
    _initialized = true;
  }

  /// Interrupts any ongoing utterance and speaks [phrase] unless muted.
  Future<void> say(String phrase) async {
    if (isMuted) return;
    if (!_initialized) {
      await initialize();
    }
    await _tts.stop();
    await _tts.speak(phrase);
  }

  Future<void> stop() async {
    await _tts.stop();
  }

  Future<void> dispose() async {
    await _tts.stop();
  }
}
