import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'dart:typed_data';

import 'package:innersight_mobile/src/announcer.dart';
import 'package:innersight_mobile/src/card_picture.dart';
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/frame_prep.dart';
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
final _unsureGreenTwo = _makeCard(CardColor.green, '2', confidence: 0.6);
final _redSevenTooClose = RecognizedCard(
  detection: _redSeven.detection,
  color: _redSeven.color,
  isTooClose: true,
);
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

  /// The time of a clock that stands still until a test moves it.
  late DateTime now;

  /// Starts a session and forgets the greeting.
  GuessingSession startSession({int cardCount = 2, bool speaksResult = false}) {
    final session = GuessingSession(
      cardCount: cardCount,
      say: spoken.add,
      speaksResult: speaksResult,
      now: () => now,
    );
    spoken.clear();
    return session;
  }

  setUp(() {
    spoken = [];
    now = DateTime(2026, 11, 25);
  });

  group('GuessingSession', () {
    test('says the machine is ready when the session starts', () {
      GuessingSession(cardCount: 2, say: spoken.add);

      expect(spoken, [readyPhrase]);
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

    test('asks for the next card after locking in', () {
      final session = startSession(cardCount: 3);

      _playRound(session, _redSeven, GuessOutcome.miss);

      expect(spoken.last, nextCardPhrase);
    });

    test('asks for the last card when one card is left', () {
      final session = startSession(cardCount: 3);
      _playRound(session, _redSeven, GuessOutcome.miss);

      _playRound(session, _blueSkip, GuessOutcome.miss);

      expect(spoken.last, lastCardPhrase);
    });

    test('reports the card that starts a round on the frame it settles', () {
      final session = startSession();
      final framesBeforeSettling = [
        for (var i = 0; i < stableFrameCount - 1; i++)
          session.observe([_redSeven]),
      ];

      final roundCard = session.observe([_redSeven]);

      expect(framesBeforeSettling, everyElement(isNull));
      expect(roundCard, _redSeven);
    });

    test('reports no card for the back of a card', () {
      final session = startSession();
      for (var i = 0; i < stableFrameCount - 1; i++) {
        session.observe([_cardBack]);
      }

      final roundCard = session.observe([_cardBack]);

      expect(roundCard, isNull);
    });

    test('corrects the card of the round when a surer reading settles', () {
      final session = startSession();
      _holdUp(session, _redSeven);

      _holdUp(session, _blueSkip);

      expect(session.card, _blueSkip);
      expect(spoken, ['red seven', 'Correction. blue skip']);
    });

    test('reports the corrected card on the frame it settles', () {
      final session = startSession();
      _holdUp(session, _redSeven);
      for (var i = 0; i < stableFrameCount - 1; i++) {
        session.observe([_blueSkip]);
      }

      final roundCard = session.observe([_blueSkip]);

      expect(roundCard, _blueSkip);
    });

    test('drops the answer given to a card that is corrected', () {
      final session = startSession();
      _holdUp(session, _redSeven);
      session.giveAnswer(GuessOutcome.bothRight);

      _holdUp(session, _blueSkip);

      expect(session.answer, isNull);
    });

    test('keeps the card of the round when the other reading is less sure', () {
      final session = startSession();
      _holdUp(session, _redSeven);

      _holdUp(session, _unsureGreenTwo);

      expect(session.card, _redSeven);
      expect(spoken, ['red seven']);
    });

    test('corrects the card until the time for corrections is up', () {
      final session = startSession();
      _holdUp(session, _redSeven);

      now = now.add(correctionTime);
      _holdUp(session, _blueSkip);

      expect(session.card, _blueSkip);
    });

    test('keeps the card of the round once the time for corrections is up', () {
      final session = startSession();
      _holdUp(session, _redSeven);

      now = now.add(correctionTime + const Duration(milliseconds: 100));
      _holdUp(session, _blueSkip);

      expect(session.card, _redSeven);
      expect(spoken, ['red seven']);
    });

    test('does not correct a card to the back of a card', () {
      final session = startSession();
      _holdUp(session, _redSeven);

      _holdUp(session, _cardBack);

      expect(session.card, _redSeven);
      expect(spoken, ['red seven']);
    });

    test('starts a round with a card held too close and says so', () {
      final session = startSession();

      _holdUp(session, _redSevenTooClose);

      expect(session.card, _redSevenTooClose);
      expect(spoken, ['red seven. Too close']);
    });

    test('says the card of the round again when it is moved too close', () {
      final session = startSession();
      _holdUp(session, _redSeven);
      session.giveAnswer(GuessOutcome.colorRight);
      spoken.clear();

      for (var i = 0; i < stableFrameCount; i++) {
        session.observe([_redSevenTooClose]);
      }

      expect(spoken, ['red seven. Too close']);
      expect(session.answer, GuessOutcome.colorRight);
    });

    test('warns without a name about a card too close between rounds', () {
      final session = startSession(cardCount: 3);
      _playRound(session, _redSeven, GuessOutcome.miss);
      spoken.clear();

      for (var i = 0; i < stableFrameCount; i++) {
        session.observe([_redSevenTooClose]);
      }

      expect(spoken, ['Too close']);
    });

    test('does not start the next round with the card still in view', () {
      final session = startSession();
      _playRound(session, _redSeven, GuessOutcome.miss);

      for (var i = 0; i < stableFrameCount * 3; i++) {
        session.observe([_redSeven]);
      }

      expect(session.card, isNull);
      expect(spoken.last, lastCardPhrase);
    });

    test('reads the back of a card aloud without starting a round', () {
      final session = startSession();

      _holdUp(session, _cardBack);

      expect(spoken, ['card back']);
      expect(session.card, isNull);
    });

    test('says only that the session is finished when the result is not '
        'spoken', () {
      final session = startSession(cardCount: 2);

      _playRound(session, _redSeven, GuessOutcome.miss);
      _playRound(session, _blueSkip, GuessOutcome.bothRight);

      expect(spoken.last, sessionFinishedPhrase);
    });

    test('finishes after the chosen number of cards and says the result', () {
      final session = startSession(cardCount: 2, speaksResult: true);

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

  group('cropCardPicture', () {
    test('cuts the pixels inside the box out of the frame as RGBA', () {
      // A frame 3 wide and 2 high, where every pixel has its index as red.
      final frame = PreparedFrame(
        rgbBytes: Uint8List.fromList([
          for (var pixel = 0; pixel < 6; pixel++) ...[pixel, 100, 200],
        ]),
        uprightWidth: 3,
        uprightHeight: 2,
        inputTensor: Float32List(0),
        inputSize: 640,
        letterboxScale: 1,
        padLeft: 0,
        padTop: 0,
      );

      final picture = cropCardPicture(
        frame,
        const Box(x1: 1, y1: 0, x2: 3, y2: 2),
      );

      expect((picture.width, picture.height), (2, 2));
      expect(picture.rgbaBytes, [
        ...[1, 100, 200, 255],
        ...[2, 100, 200, 255],
        ...[4, 100, 200, 255],
        ...[5, 100, 200, 255],
      ]);
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

      final picture = CardPicture(
        rgbaBytes: Uint8List(2 * 3 * 4),
        width: 2,
        height: 3,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ResultBoard(
              rounds: rounds,
              pictures: [picture, picture],
              onDone: () {},
            ),
          ),
        ),
      );

      expect(find.byType(CardPictureView), findsNWidgets(2));
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
