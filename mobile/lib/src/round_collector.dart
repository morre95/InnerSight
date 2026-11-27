import 'package:flutter/foundation.dart';

import 'card_picture.dart';
import 'cards.dart';
import 'example_uploader.dart';

/// How far the frame of a round has come on its way to the inbox.
enum SendStatus { notSent, sending, sent, failed }

/// Sends the frames of the rounds of a game away as training examples, and
/// knows how far each one has come.
///
/// The frames are kept in memory until the game screen is left. A frame that
/// was not sent by then is gone, as the app stores no pictures.
class RoundCollector extends ChangeNotifier {
  RoundCollector({required this.uploader, required this.config});

  final ExampleUploader uploader;

  /// The ranks a true card can have.
  final ModelConfig config;

  final List<RoundFrame> _frames = [];
  final Map<int, SendStatus> _statuses = {};
  final Map<int, String> _errors = {};
  bool _isDisposed = false;

  /// Takes in the frame of the round that was just locked in.
  void addRound(RoundFrame frame) => _frames.add(frame);

  /// The frame of the round at [index], counted from zero.
  RoundFrame frameOf(int index) => _frames[index];

  SendStatus statusOf(int index) => _statuses[index] ?? SendStatus.notSent;

  /// Why the frame of the round was not sent, when its status is failed.
  String? errorOf(int index) => _errors[index];

  /// Sends the frame of the round at [index] as an example of [trueCard].
  Future<void> send(int index, CardFace trueCard) async {
    _update(index, SendStatus.sending);
    try {
      await uploader.upload(_frames[index], trueCard);
      _update(index, SendStatus.sent);
    } on UploadException catch (error) {
      _update(index, SendStatus.failed, error: error.message);
    }
  }

  void _update(int index, SendStatus status, {String? error}) {
    // An upload may finish after the screen was left; nobody is told then.
    if (_isDisposed) return;
    _statuses[index] = status;
    if (error == null) {
      _errors.remove(index);
    } else {
      _errors[index] = error;
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _isDisposed = true;
    super.dispose();
  }
}
