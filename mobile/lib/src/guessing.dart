import 'announcer.dart';
import 'cards.dart';

const String firstCardPhrase = 'Hold up your first card';
const String nextCardPhrase = 'Locked in. Next card';
const String lastCardPhrase = 'Locked in. Last card';
const String noCardPhrase = 'Hold up a card first';
const String noAnswerPhrase = 'Answer first';
const String sessionFinishedPhrase = 'Session finished';

/// Said before the name of the card when the reading of a round is corrected.
const String correctionPhrase = 'Correction';

/// How long after a card is first read a surer reading may still replace it.
/// After that, another card in view is taken for the next card held up too
/// early, and is ignored.
const Duration correctionTime = Duration(seconds: 5);

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
///
/// [now] gives the current time; it is the clock of the device by default.
/// With [speaksResult] the count of every answer is said when the session
/// ends; without it the voice only says that the session is finished.
class GuessingSession {
  GuessingSession({
    required this.cardCount,
    required this.say,
    this.spokenRanks = defaultSpokenRanks,
    this.speaksResult = false,
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now {
    say(firstCardPhrase);
  }

  final int cardCount;
  final void Function(String phrase) say;
  final Map<String, String> spokenRanks;
  final bool speaksResult;
  final DateTime Function() _now;

  final CardWatcher _watcher = CardWatcher();
  final List<GuessRound> _rounds = [];
  RecognizedCard? _card;
  DateTime? _roundStartedAt;
  GuessOutcome? _answer;

  /// The rounds that are locked in, in the order they were played.
  List<GuessRound> get rounds => List.unmodifiable(_rounds);

  /// The card of the round being played, or null while waiting for a card.
  RecognizedCard? get card => _card;

  /// The latest answer in the round being played.
  GuessOutcome? get answer => _answer;

  bool get isFinished => _rounds.length == cardCount;

  /// Takes in the cards recognized in one frame; returns the card of the
  /// round if it changed.
  ///
  /// A card that settles in view while no round is being played starts the
  /// next round. The back of a card is read aloud but starts no round. While
  /// a round is being played, a surer reading may correct its card for a
  /// short time. On every frame that neither starts a round nor corrects its
  /// card, null is returned.
  ///
  /// A card held too close to the camera is still read, and the player is
  /// told to move it.
  RecognizedCard? observe(List<RecognizedCard> cards) {
    final sighting = _watcher.observe(cards);
    if (isFinished) {
      return null;
    }
    var (roundCard, phrase) = _takeIn(sighting.settledCard);
    if (sighting.isTooCloseWarningDue) {
      // Without a new name to say, the name of the card being played is said
      // again.
      final card = _card;
      final name = card == null ? null : _spokenName(card);
      phrase = withTooCloseWarning(phrase ?? name);
    }
    if (phrase != null) {
      say(phrase);
    }
    return roundCard;
  }

  String _spokenName(RecognizedCard card) =>
      spokenName(card.face, spokenRanks: spokenRanks);

  /// Lets a card that settled start or correct a round.
  ///
  /// Returns the card of the round if it changed, and what to say about the
  /// settled card.
  (RecognizedCard?, String?) _takeIn(RecognizedCard? settledCard) {
    if (settledCard == null) {
      return (null, null);
    }
    final card = _card;
    if (card != null) {
      return _correctCard(card, settledCard);
    }
    final name = _spokenName(settledCard);
    if (settledCard.color == CardColor.back) {
      return (null, name);
    }
    _card = settledCard;
    _roundStartedAt = _now();
    return (settledCard, name);
  }

  /// Replaces the card of the round with another reading that the model is
  /// surer of.
  ///
  /// A card misread at a distance is often read right once it is held closer.
  /// The answer given so far is dropped, as it was an answer to the card that
  /// was read first. Returns the new card of the round and what to say, or
  /// neither if the reading is not taken.
  (RecognizedCard?, String?) _correctCard(
    RecognizedCard card,
    RecognizedCard settledCard,
  ) {
    final isOtherCard =
        settledCard.face != card.face && settledCard.color != CardColor.back;
    final isSurer =
        settledCard.detection.confidence > card.detection.confidence;
    final isInTime = _now().difference(_roundStartedAt!) <= correctionTime;
    if (!(isOtherCard && isSurer && isInTime)) {
      return (null, null);
    }
    _card = settledCard;
    _answer = null;
    return (settledCard, '$correctionPhrase. ${_spokenName(settledCard)}');
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
    say(_phraseAfterLockingIn());
    return lockedRound;
  }

  String _phraseAfterLockingIn() {
    final cardsLeft = cardCount - _rounds.length;
    if (cardsLeft == 0) {
      return speaksResult ? spokenSummary(_rounds) : sessionFinishedPhrase;
    }
    return cardsLeft == 1 ? lastCardPhrase : nextCardPhrase;
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
  return '$sessionFinishedPhrase. $counts.';
}
