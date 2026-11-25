import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/frame_prep.dart';
import 'package:innersight_mobile/src/home_screen.dart';
import 'package:innersight_mobile/src/recognition.dart';

class _NeverCalledDetector implements CardDetector {
  @override
  Future<List<Detection>> detect(
    PreparedFrame frame, {
    required double minConfidence,
  }) async => const [];
}

Future<CardModel> _loadAtOnce() async =>
    (detector: _NeverCalledDetector(), config: ModelConfig.defaults());

void main() {
  Future<void> openHomeScreen(
    WidgetTester tester, {
    Future<CardModel> Function() loadCardModel = _loadAtOnce,
  }) async {
    await tester.pumpWidget(
      MaterialApp(home: HomeScreen(loadCardModel: loadCardModel)),
    );
    await tester.pump();
  }

  group('HomeScreen', () {
    testWidgets('offers no game while the model is loading', (tester) async {
      final loading = Completer<CardModel>();

      await openHomeScreen(tester, loadCardModel: () => loading.future);

      expect(find.text('Loading the card model...'), findsOneWidget);
      expect(find.text('Start game'), findsNothing);
    });

    testWidgets('offers a game once the model is loaded', (tester) async {
      await openHomeScreen(tester);

      expect(find.text('Start game'), findsOneWidget);
    });

    testWidgets('offers to try again when the model could not be loaded', (
      tester,
    ) async {
      await openHomeScreen(
        tester,
        loadCardModel: () async => throw StateError('no model'),
      );

      expect(find.text('The card model could not be loaded.'), findsOneWidget);
      expect(find.text('Start game'), findsNothing);
    });

    testWidgets('loads the model when asked to try again', (tester) async {
      var attempts = 0;
      await openHomeScreen(
        tester,
        loadCardModel: () {
          attempts += 1;
          return attempts == 1
              ? Future.error(StateError('no model'))
              : _loadAtOnce();
        },
      );

      await tester.tap(find.text('Try again'));
      await tester.pump();

      expect(find.text('Start game'), findsOneWidget);
    });

    testWidgets('hides the advanced settings at first', (tester) async {
      await openHomeScreen(tester);

      expect(find.text('Read a card when 50% sure'), findsNothing);
      expect(find.text('Just read cards aloud'), findsNothing);
    });

    testWidgets('shows the confidence and reading aloud under Advanced', (
      tester,
    ) async {
      await openHomeScreen(tester);

      await tester.tap(find.text('Advanced'));
      await tester.pump();

      expect(find.text('Read a card when 50% sure'), findsOneWidget);
      expect(find.text('Just read cards aloud'), findsOneWidget);
    });

    testWidgets('hides the advanced settings again on a second tap', (
      tester,
    ) async {
      await openHomeScreen(tester);
      await tester.tap(find.text('Advanced'));
      await tester.pump();

      await tester.tap(find.text('Advanced'));
      await tester.pump();

      expect(find.text('Just read cards aloud'), findsNothing);
    });
  });
}
