import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:innersight_mobile/src/announcer.dart';
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/game_screen.dart';
import 'package:innersight_mobile/src/guessing.dart';
import 'package:innersight_mobile/src/result_board.dart';

RecognizedCard _makeCard(
  CardColor color,
  String rank, {
  double confidence = 0.9,
}) {
  return RecognizedCard(
    detection: Detection(
      rank: rank,
      confidence: confidence,
      box: const Box(x1: 0, y1: 0, x2: 10, y2: 10),
    ),
    color: color,
  );
}

final _redSeven = _makeCard(CardColor.red, '7', confidence: 0.8);
final _blueSkip = _makeCard(CardColor.blue, 'skip');
final _cardBack = _makeCard(CardColor.back, 'back');

/// Takes the last card away and holds up [card] until it settles.
void _holdUp(GuessingSession session, RecognizedCard card) {
  for (final cards in [
    const <RecognizedCard>[],
    [card],
  ]) {
    for (var i = 0; i < stableFrameCount; i++) {
      session.observe(cards);
    }
  }
}

void _playRound(
  GuessingSession session,
  RecognizedCard card,
  GuessOutcome outcome,
) {
  _holdUp(session, card);
  session.giveAnswer(outcome);
  session.lockIn();
}

void main() {
  late List<String> spoken;

  /// Starts a session and forgets the greeting.
  GuessingSession startSession({int cardCount = 2}) {
    final session = GuessingSession(cardCount: cardCount, say: spoken.add);
    spoken.clear();
    return session;
  }

  setUp(() => spoken = []);

  group('GuessingSession', () {
    test('asks for the first card when the session starts', () {
      GuessingSession(cardCount: 2, say: spoken.add);

      expect(spoken, [firstCardPhrase]);
    });

    test('reads a card aloud once it has settled in view', () {
      final session = startSession();

      _holdUp(session, _redSeven);

      expect(spoken, ['red seven']);
    });

    test('counts only the last answer given before locking in', () {
      final session = startSession();
      _holdUp(session, _redSeven);

      session.giveAnswer(GuessOutcome.miss);
      session.giveAnswer(GuessOutcome.colorRight);
      session.giveAnswer(GuessOutcome.bothRight);
      session.lockIn();

      expect(spoken.sublist(1, 4), ['miss', 'color right', 'both right']);
      expect(session.rounds.single.outcome, GuessOutcome.bothRight);
    });

    test('logs the card the model read and how sure it was', () {
      final session = startSession();
      _holdUp(session, _redSeven);
      session.giveAnswer(GuessOutcome.miss);

      final lockedRound = session.lockIn()!;

      expect(lockedRound.face, _redSeven.face);
      expect(lockedRound.confidence, 0.8);
    });

    test('says an answer without counting it while no card is read', () {
      final session = startSession();

      session.giveAnswer(GuessOutcome.rankRight);
      _holdUp(session, _redSeven);

      expect(spoken.first, 'rank right');
      expect(session.answer, isNull);
    });

    test('does not lock in before a card is read', () {
      final session = startSession();

      expect(session.lockIn(), isNull);
      expect(spoken, [noCardPhrase]);
    });

    test('does not lock in before an answer is given', () {
      final session = startSession();
      _holdUp(session, _redSeven);

      expect(session.lockIn(), isNull);
      expect(spoken.last, noAnswerPhrase);
    });

    test('keeps the card of the round when another card comes into view', () {
      final session = startSession();
      _holdUp(session, _redSeven);

      _holdUp(session, _blueSkip);

      expect(session.card, _redSeven);
      expect(spoken, ['red seven']);
    });

    test('does not start the next round with the card still in view', () {
      final session = startSession();
      _playRound(session, _redSeven, GuessOutcome.miss);

      for (var i = 0; i < stableFrameCount * 3; i++) {
        session.observe([_redSeven]);
      }

      expect(session.card, isNull);
      expect(spoken.last, nextCardPhrase);
    });

    test('reads the back of a card aloud without starting a round', () {
      final session = startSession();

      _holdUp(session, _cardBack);

      expect(spoken, ['card back']);
      expect(session.card, isNull);
    });

    test('finishes after the chosen number of cards and says the result', () {
      final session = startSession(cardCount: 2);

      _playRound(session, _redSeven, GuessOutcome.miss);
      final wasFinishedAfterOneCard = session.isFinished;
      _playRound(session, _blueSkip, GuessOutcome.bothRight);

      expect(wasFinishedAfterOneCard, isFalse);
      expect(session.isFinished, isTrue);
      expect(
        spoken.last,
        'Session finished. both right 1, color right 0, rank right 0, miss 1.',
      );
    });
  });

  group('swipeOutcome', () {
    test('maps each swipe direction to its answer', () {
      expect(swipeOutcome(const Offset(0, -120)), GuessOutcome.bothRight);
      expect(swipeOutcome(const Offset(-120, 0)), GuessOutcome.colorRight);
      expect(swipeOutcome(const Offset(120, 0)), GuessOutcome.rankRight);
      expect(swipeOutcome(const Offset(0, 120)), GuessOutcome.miss);
    });

    test('goes by the main direction of a slanted swipe', () {
      expect(swipeOutcome(const Offset(-30, -120)), GuessOutcome.bothRight);
      expect(swipeOutcome(const Offset(120, 40)), GuessOutcome.rankRight);
    });

    test('ignores a drag too short to be a swipe', () {
      expect(swipeOutcome(const Offset(10, -20)), isNull);
    });
  });

  group('ResultBoard', () {
    testWidgets('shows the count of every outcome and every card read', (
      tester,
    ) async {
      final rounds = [
        GuessRound(
          face: _redSeven.face,
          confidence: 0.8,
          outcome: GuessOutcome.bothRight,
        ),
        GuessRound(
          face: _blueSkip.face,
          confidence: 0.61,
          outcome: GuessOutcome.miss,
        ),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ResultBoard(rounds: rounds, onDone: () {}),
          ),
        ),
      );

      expect(find.text('Session result: 2 cards'), findsOneWidget);
      expect(find.text('1   50%'), findsNWidgets(2));
      expect(find.text('0   0%'), findsNWidgets(2));
      expect(find.text('red 7'), findsOneWidget);
      expect(find.text('Model 80% sure'), findsOneWidget);
      expect(find.text('blue skip'), findsOneWidget);
      expect(find.text('Model 61% sure'), findsOneWidget);
    });
  });
}
