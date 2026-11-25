import 'cards.dart';

/// Number of consecutive frames a card must stay in view, or absent, to settle.
const int stableFrameCount = 5;

const String tooClosePhrase = 'Too close';

/// Converts a [CardFace] into its spoken English phrase (e.g. "red seven", "card back").
String spokenName(
  CardFace face, {
  Map<String, String> spokenRanks = defaultSpokenRanks,
}) {
  return face.describe(spokenRanks[face.rank] ?? face.rank);
}

/// Follows a value that is read anew in every frame, and tells when it has
/// settled: when it has been the same for [stableFrameCount] frames in a row.
///
/// Direct port of `SettlingValue` in `src/innersight/announcement.py`.
class SettlingValue<Value> {
  SettlingValue(this._initial) : _candidate = _initial, _settled = _initial;

  final Value _initial;
  Value _candidate;
  int _candidateFrameCount = 0;
  Value _settled;

  /// The value that last settled.
  Value get settled => _settled;

  /// Takes in the value of one frame; tells whether it settles on something
  /// new in it.
  bool observe(Value value) {
    if (value == _candidate) {
      _candidateFrameCount += 1;
    } else {
      _candidate = value;
      _candidateFrameCount = 1;
    }

    final isSettled = _candidateFrameCount == stableFrameCount;
    if (!isSettled || value == _settled) {
      return false;
    }
    _settled = value;
    return true;
  }

  void reset() {
    _candidate = _initial;
    _candidateFrameCount = 0;
    _settled = _initial;
  }
}

RecognizedCard? _surest(Iterable<RecognizedCard> cards) {
  RecognizedCard? best;
  for (final card in cards) {
    if (best == null || card.detection.confidence > best.detection.confidence) {
      best = card;
    }
  }
  return best;
}

/// Reports a card once when it settles in view, and again only after a change.
///
/// Direct port of `SettledCardWatcher` in `src/innersight/announcement.py`.
class SettledCardWatcher {
  final SettlingValue<CardFace?> _face = SettlingValue(null);

  /// The face that last settled in view, or null when no card is in view.
  CardFace? get settled => _face.settled;

  /// Takes in the cards of one frame. With several, the surest one counts.
  ///
  /// Returns the card on the frame it settles in view, and null otherwise.
  ///
  /// A card whose color could not be read is not a card that exists, such as
  /// "unknown 5". A frame that shows only such cards is left out, so the card
  /// is read again in the next frame, and neither settles under a wrong name
  /// nor counts as taken away.
  RecognizedCard? observe(List<RecognizedCard> cards) {
    final card = _surest(
      cards.where((card) => card.color != CardColor.unknown),
    );
    if (cards.isNotEmpty && card == null) {
      return null;
    }
    return _face.observe(card?.face) ? card : null;
  }

  void reset() => _face.reset();
}

/// Tells once when a card is held too close to the camera, and again only
/// after it was not.
///
/// Direct port of `TooCloseWatcher` in `src/innersight/announcement.py`.
class TooCloseWatcher {
  final SettlingValue<bool> _isTooClose = SettlingValue(false);

  /// Takes in the cards of one frame. With several, the surest one counts.
  ///
  /// Returns true on the frame the card has settled too close.
  bool observe(List<RecognizedCard> cards) {
    final isTooClose = _surest(cards)?.isTooClose ?? false;
    return _isTooClose.observe(isTooClose) && isTooClose;
  }

  void reset() => _isTooClose.reset();
}

/// Adds the warning that the card is too close to what is said, if anything.
///
/// A new phrase cuts off the one being spoken. So when the warning comes while
/// the name of the card is spoken, it has to say the name again, or the player
/// never hears it.
String withTooCloseWarning(String? phrase) {
  return phrase == null ? tooClosePhrase : '$phrase. $tooClosePhrase';
}

/// Announces a card once when it settles in view, and again only after a
/// change. Also says when the card is held too close to the camera.
///
/// Direct port of `CardAnnouncer` in `src/innersight/announcement.py`.
class CardAnnouncer {
  CardAnnouncer({required this.say, this.spokenRanks = defaultSpokenRanks});

  final void Function(String phrase) say;
  final Map<String, String> spokenRanks;
  final SettledCardWatcher _watcher = SettledCardWatcher();
  final TooCloseWatcher _tooCloseWatcher = TooCloseWatcher();

  CardFace? get announced => _watcher.settled;

  void observe(List<RecognizedCard> cards) {
    final card = _watcher.observe(cards);
    if (_tooCloseWatcher.observe(cards)) {
      final face = _watcher.settled;
      say(
        withTooCloseWarning(
          face == null ? null : spokenName(face, spokenRanks: spokenRanks),
        ),
      );
    } else if (card != null) {
      say(spokenName(card.face, spokenRanks: spokenRanks));
    }
  }

  void reset() {
    _watcher.reset();
    _tooCloseWatcher.reset();
  }
}
