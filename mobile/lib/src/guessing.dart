import 'announcer.dart';
import 'cards.dart';

const String firstCardPhrase = 'Hold up your first card';
const String nextCardPhrase = 'Locked in. Next card';
const String noCardPhrase = 'Hold up a card first';
const String noAnswerPhrase = 'Answer first';

/// How a guess turned out. [phrase] is what the voice says for it.
enum GuessOutcome {
  bothRight('both right'),
  colorRight('color right'),
  rankRight('rank right'),
  miss('miss');

  const GuessOutcome(this.phrase);
  final String phrase;
}

/// One card of a session: what the model read, how sure it was, and how the
/// guess went.
class GuessRound {
  const GuessRound({
    required this.face,
    required this.confidence,
    required this.outcome,
  });

  final CardFace face;
  final double confidence;
  final GuessOutcome outcome;
}

/// Runs the rounds of one game and speaks every step, so it can be played
/// blindfolded.
///
/// A round starts when a card settles in view and is read aloud. The player
/// then answers as often as they like; the last answer counts once they lock
/// it in. Direct port of `GuessingSession` in `src/innersight/guessing.py`.
class GuessingSession {
  GuessingSession({
    required this.cardCount,
    required this.say,
    this.spokenRanks = defaultSpokenRanks,
  }) {
    say(firstCardPhrase);
  }

  final int cardCount;
  final void Function(String phrase) say;
  final Map<String, String> spokenRanks;

  final SettledCardWatcher _watcher = SettledCardWatcher();
  final List<GuessRound> _rounds = [];
  RecognizedCard? _card;
  GuessOutcome? _answer;

  /// The rounds that are locked in, in the order they were played.
  List<GuessRound> get rounds => List.unmodifiable(_rounds);

  /// The card of the round being played, or null while waiting for a card.
  RecognizedCard? get card => _card;

  /// The latest answer in the round being played.
  GuessOutcome? get answer => _answer;

  bool get isFinished => _rounds.length == cardCount;

  /// Takes in the cards recognized in one frame.
  ///
  /// A card that settles in view while no round is being played starts the
  /// next round. The back of a card is read aloud but starts no round.
  void observe(List<RecognizedCard> cards) {
    final settledCard = _watcher.observe(cards);
    if (settledCard == null || _card != null || isFinished) {
      return;
    }
    say(spokenName(settledCard.face, spokenRanks: spokenRanks));
    if (settledCard.color != CardColor.back) {
      _card = settledCard;
    }
  }

  /// Says the outcome, and makes it the answer of the round being played.
  ///
  /// Between rounds it is only said, so the player can learn the swipes by ear.
  void giveAnswer(GuessOutcome outcome) {
    say(outcome.phrase);
    if (_card != null) {
      _answer = outcome;
    }
  }

  /// Ends the round with its latest answer.
  ///
  /// Returns the round, or null if there is no card or no answer yet.
  GuessRound? lockIn() {
    final card = _card;
    final answer = _answer;
    if (card == null) {
      say(noCardPhrase);
      return null;
    }
    if (answer == null) {
      say(noAnswerPhrase);
      return null;
    }
    final lockedRound = GuessRound(
      face: card.face,
      confidence: card.detection.confidence,
      outcome: answer,
    );
    _rounds.add(lockedRound);
    _card = null;
    _answer = null;
    say(isFinished ? spokenSummary(_rounds) : nextCardPhrase);
    return lockedRound;
  }
}

/// How many rounds ended with each outcome, with every outcome present.
Map<GuessOutcome, int> countOutcomes(List<GuessRound> rounds) {
  return {
    for (final outcome in GuessOutcome.values)
      outcome: rounds.where((round) => round.outcome == outcome).length,
  };
}

/// What the voice says when a session ends.
String spokenSummary(List<GuessRound> rounds) {
  final counts = countOutcomes(
    rounds,
  ).entries.map((entry) => '${entry.key.phrase} ${entry.value}').join(', ');
  return 'Session finished. $counts.';
}
