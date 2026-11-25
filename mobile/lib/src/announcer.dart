import 'cards.dart';

/// Number of consecutive frames a card must stay in view, or absent, to settle.
const int stableFrameCount = 5;

/// Converts a [CardFace] into its spoken English phrase (e.g. "red seven", "card back").
String spokenName(
  CardFace face, {
  Map<String, String> spokenRanks = defaultSpokenRanks,
}) {
  return face.describe(spokenRanks[face.rank] ?? face.rank);
}

/// Reports a card once when it settles in view, and again only after a change.
///
/// Direct port of `SettledCardWatcher` in `src/innersight/announcement.py`.
class SettledCardWatcher {
  CardFace? _candidate;
  int _candidateFrameCount = 0;
  CardFace? _settled;

  /// The face that last settled in view, or null when no card is in view.
  CardFace? get settled => _settled;

  /// Takes in the cards of one frame. With several, the surest one counts.
  ///
  /// Returns the card on the frame it settles in view, and null otherwise.
  RecognizedCard? observe(List<RecognizedCard> cards) {
    RecognizedCard? best;
    for (final card in cards) {
      if (best == null ||
          card.detection.confidence > best.detection.confidence) {
        best = card;
      }
    }
    final face = best?.face;

    if (face == _candidate) {
      _candidateFrameCount += 1;
    } else {
      _candidate = face;
      _candidateFrameCount = 1;
    }

    final isSettled = _candidateFrameCount == stableFrameCount;
    if (!isSettled || face == _settled) {
      return null;
    }
    _settled = face;
    return best;
  }

  void reset() {
    _candidate = null;
    _candidateFrameCount = 0;
    _settled = null;
  }
}

/// Announces a card once when it settles in view, and again only after a change.
///
/// Direct port of `CardAnnouncer` in `src/innersight/announcement.py`.
class CardAnnouncer {
  CardAnnouncer({required this.say, this.spokenRanks = defaultSpokenRanks});

  final void Function(String phrase) say;
  final Map<String, String> spokenRanks;
  final SettledCardWatcher _watcher = SettledCardWatcher();

  CardFace? get announced => _watcher.settled;

  void observe(List<RecognizedCard> cards) {
    final card = _watcher.observe(cards);
    if (card != null) {
      say(spokenName(card.face, spokenRanks: spokenRanks));
    }
  }

  void reset() => _watcher.reset();
}
