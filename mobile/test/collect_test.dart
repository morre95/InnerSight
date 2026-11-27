import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:innersight_mobile/src/card_picture.dart';
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/example_uploader.dart';
import 'package:innersight_mobile/src/guessing.dart';
import 'package:innersight_mobile/src/result_board.dart';
import 'package:innersight_mobile/src/round_collector.dart';
import 'package:innersight_mobile/src/true_card_screen.dart';

const _redSix = RecognizedCard(
  detection: Detection(
    rank: '6',
    confidence: 0.62,
    box: Box(x1: 0, y1: 0, x2: 2, y2: 3),
  ),
  color: CardColor.red,
);

RoundFrame _frameOf(RecognizedCard card) {
  return RoundFrame(
    rgbBytes: Uint8List(2 * 3 * 3),
    width: 2,
    height: 3,
    card: card,
  );
}

/// Stands in for the inbox: remembers what was sent, and can refuse it.
class _FakeUploader implements ExampleUploader {
  final List<(RoundFrame, CardFace)> sent = [];

  /// When set, every upload is refused with this message.
  String? refusal;

  /// When set, an upload does not finish until this does.
  Completer<void>? hold;

  @override
  Future<void> upload(RoundFrame frame, CardFace trueCard) async {
    await hold?.future;
    final refusal = this.refusal;
    if (refusal != null) {
      throw UploadException(refusal);
    }
    sent.add((frame, trueCard));
  }
}

/// Scrolls the choices until [chip] is in view, as a tap outside the view
/// hits nothing, and taps it.
Future<void> _chooseChip(WidgetTester tester, String chip) async {
  // A chip below the view is built but off stage, so it is looked for there.
  final finder = find.widgetWithText(ChoiceChip, chip, skipOffstage: false);
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

RoundCollector _collectorWith(_FakeUploader uploader) {
  final collector = RoundCollector(
    uploader: uploader,
    config: ModelConfig.defaults(),
  );
  collector.addRound(_frameOf(_redSix));
  return collector;
}

void main() {
  const redNine = CardFace(color: CardColor.red, rank: '9');

  group('RoundCollector', () {
    test('has sent nothing before the player asks for it', () {
      final collector = _collectorWith(_FakeUploader());

      expect(collector.statusOf(0), SendStatus.notSent);
    });

    test('marks a round as sent once its upload succeeds', () async {
      final uploader = _FakeUploader();
      final collector = _collectorWith(uploader);

      await collector.send(0, redNine);

      expect(collector.statusOf(0), SendStatus.sent);
      expect(uploader.sent.single.$2, redNine);
    });

    test('is sending while the upload is on its way', () async {
      final uploader = _FakeUploader()..hold = Completer<void>();
      final collector = _collectorWith(uploader);

      final sending = collector.send(0, redNine);

      expect(collector.statusOf(0), SendStatus.sending);
      uploader.hold!.complete();
      await sending;
    });

    test('tells why a round was not sent when the upload fails', () async {
      final uploader = _FakeUploader()..refusal = 'The token is not valid';
      final collector = _collectorWith(uploader);

      await collector.send(0, redNine);

      expect(collector.statusOf(0), SendStatus.failed);
      expect(collector.errorOf(0), 'The token is not valid');
    });

    test('forgets the failure when the round is sent again', () async {
      final uploader = _FakeUploader()..refusal = 'The token is not valid';
      final collector = _collectorWith(uploader);
      await collector.send(0, redNine);

      uploader.refusal = null;
      await collector.send(0, redNine);

      expect(collector.statusOf(0), SendStatus.sent);
      expect(collector.errorOf(0), isNull);
    });

    test(
      'tells nobody of an upload that ends after the screen is left',
      () async {
        final uploader = _FakeUploader()..hold = Completer<void>();
        final collector = _collectorWith(uploader);
        final sending = collector.send(0, redNine);

        collector.dispose();
        uploader.hold!.complete();

        await expectLater(sending, completes);
      },
    );
  });

  group('TrueCardScreen', () {
    Future<List<CardFace?>> open(
      WidgetTester tester,
      RecognizedCard card,
    ) async {
      final popped = <CardFace?>[];
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => TextButton(
              onPressed: () async {
                popped.add(
                  await Navigator.of(context).push<CardFace>(
                    MaterialPageRoute(
                      builder: (_) => TrueCardScreen(
                        frame: _frameOf(card),
                        config: ModelConfig.defaults(),
                      ),
                    ),
                  ),
                );
              },
              child: const Text('open'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      return popped;
    }

    Future<void> choose(WidgetTester tester, String chip) {
      return _chooseChip(tester, chip);
    }

    Future<void> send(WidgetTester tester) async {
      await tester.tap(find.text('Send'));
      await tester.pumpAndSettle();
    }

    testWidgets('starts at the card the model read', (tester) async {
      await open(tester, _redSix);

      expect(find.text('True card: red 6'), findsOneWidget);
    });

    testWidgets('gives back the rank and the color that were chosen', (
      tester,
    ) async {
      final popped = await open(tester, _redSix);

      await choose(tester, '9');
      await choose(tester, 'blue');
      await send(tester);

      expect(popped, [const CardFace(color: CardColor.blue, rank: '9')]);
    });

    testWidgets('a wild rank is wild whatever suit is chosen', (tester) async {
      final popped = await open(tester, _redSix);

      await choose(tester, '+4');
      await send(tester);

      expect(popped, [const CardFace(color: CardColor.wild, rank: '+4')]);
    });

    testWidgets('greys out the colors for a wild card', (tester) async {
      await open(tester, _redSix);

      await choose(tester, 'wild');

      final redChip = tester.widget<ChoiceChip>(
        find.widgetWithText(ChoiceChip, 'red'),
      );
      expect(redChip.onSelected, isNull);
      expect(redChip.selected, isFalse);
    });

    testWidgets('gets the chosen color back after a wild rank', (tester) async {
      final popped = await open(tester, _redSix);

      await choose(tester, 'wild');
      await choose(tester, '7');
      await send(tester);

      expect(popped, [const CardFace(color: CardColor.red, rank: '7')]);
    });

    testWidgets('gives back nothing when the player goes back', (tester) async {
      final popped = await open(tester, _redSix);

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(popped, [null]);
    });
  });

  group('ResultBoard with collecting', () {
    final rounds = [
      GuessRound(
        face: _redSix.face,
        confidence: 0.62,
        outcome: GuessOutcome.miss,
      ),
    ];
    final picture = CardPicture(
      rgbaBytes: Uint8List(2 * 3 * 4),
      width: 2,
      height: 3,
    );

    Future<void> openBoard(WidgetTester tester, RoundCollector? collector) {
      return tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ResultBoard(
              rounds: rounds,
              pictures: [picture],
              collector: collector,
              onDone: () {},
            ),
          ),
        ),
      );
    }

    Future<void> sendFirstRoundAs(WidgetTester tester, String rank) async {
      await tester.tap(find.text('red 6'));
      await tester.pumpAndSettle();
      await _chooseChip(tester, rank);
      await tester.tap(find.text('Send'));
      await tester.pumpAndSettle();
    }

    testWidgets('offers no collecting unless it is turned on', (tester) async {
      await openBoard(tester, null);

      await tester.tap(find.text('red 6'));
      await tester.pumpAndSettle();

      expect(find.byTooltip('Send as a training example'), findsNothing);
      expect(find.byType(TrueCardScreen), findsNothing);
    });

    testWidgets('sends the frame of a tapped round with its true card', (
      tester,
    ) async {
      final uploader = _FakeUploader();
      final collector = _collectorWith(uploader);
      addTearDown(collector.dispose);
      await openBoard(tester, collector);

      await sendFirstRoundAs(tester, '9');

      expect(uploader.sent.single.$1.card, _redSix);
      expect(uploader.sent.single.$2, redNine);
      expect(find.byTooltip('Sent'), findsOneWidget);
    });

    testWidgets('offers to try again when the upload fails', (tester) async {
      final uploader = _FakeUploader()..refusal = 'The token is not valid';
      final collector = _collectorWith(uploader);
      addTearDown(collector.dispose);
      await openBoard(tester, collector);
      await sendFirstRoundAs(tester, '9');

      expect(find.text('The token is not valid'), findsOneWidget);
      expect(find.byTooltip('Not sent. Tap to try again'), findsOneWidget);

      uploader.refusal = null;
      await sendFirstRoundAs(tester, '9');

      expect(find.byTooltip('Sent'), findsOneWidget);
    });

    testWidgets('does not send a round that is sent a second time', (
      tester,
    ) async {
      final uploader = _FakeUploader();
      final collector = _collectorWith(uploader);
      addTearDown(collector.dispose);
      await openBoard(tester, collector);
      await sendFirstRoundAs(tester, '9');

      await tester.tap(find.text('red 6'));
      await tester.pumpAndSettle();

      expect(find.byType(TrueCardScreen), findsNothing);
    });
  });
}
