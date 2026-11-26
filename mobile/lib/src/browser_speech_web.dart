import 'dart:js_interop';

@JS('innerSightSpeech.enable')
external void enable();

@JS('innerSightSpeech.say')
external JSPromise<JSAny?> _say(JSString phrase);

Future<void> say(String phrase) async {
  await _say(phrase.toJS).toDart;
}

@JS('innerSightSpeech.stop')
external void stop();
