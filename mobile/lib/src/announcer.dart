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

/// Announces a card once when it settles in view, and again only after a change.
///
/// Direct port of `CardAnnouncer` in `src/innersight/announcement.py`.
class CardAnnouncer {
  CardAnnouncer({
    required this.say,
    this.spokenRanks = defaultSpokenRanks,
  });

  final void Function(String phrase) say;
  final Map<String, String> spokenRanks;

  CardFace? _candidate;
  int _candidateFrameCount = 0;
  CardFace? _announced;

  CardFace? get announced => _announced;

  void observe(List<RecognizedCard> cards) {
    CardFace? face;
    if (cards.isNotEmpty) {
      var best = cards.first;
      for (var i = 1; i < cards.length; i++) {
        if (cards[i].detection.confidence > best.detection.confidence) {
          best = cards[i];
        }
      }
      face = best.face;
    }

    if (face == _candidate) {
      _candidateFrameCount += 1;
    } else {
      _candidate = face;
      _candidateFrameCount = 1;
    }

    final isSettled = _candidateFrameCount == stableFrameCount;
    if (isSettled && face != _announced) {
      _announced = face;
      if (face != null) {
        say(spokenName(face, spokenRanks: spokenRanks));
      }
    }
  }

  void reset() {
    _candidate = null;
    _candidateFrameCount = 0;
    _announced = null;
  }
}
