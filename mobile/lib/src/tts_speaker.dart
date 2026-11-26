import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_tts/flutter_tts.dart';

import 'browser_speech_stub.dart'
    if (dart.library.js_interop) 'browser_speech_web.dart'
    as browser_speech;

/// Speaks recognized UNO card phrases and game prompts.
class TtsSpeaker {
  TtsSpeaker({FlutterTts? tts, this.isMuted = false})
    : _tts = tts ?? FlutterTts();

  final FlutterTts _tts;
  bool isMuted;
  bool _initialized = false;

  /// Call directly from the tap that opens a screen with announcements.
  static void enableBrowserAudio() {
    if (kIsWeb) browser_speech.enable();
  }

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
    if (kIsWeb) {
      await browser_speech.say(phrase);
      return;
    }
    if (!_initialized) {
      await initialize();
    }
    await _tts.stop();
    await _tts.speak(phrase);
  }

  Future<void> stop() async {
    if (kIsWeb) {
      browser_speech.stop();
      return;
    }
    await _tts.stop();
  }

  Future<void> dispose() => stop();
}
