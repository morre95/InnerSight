import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/collect_settings.dart';
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

/// Keeps the collect settings in memory, in place of the phone's preferences.
class _MemoryCollectSettingsStore implements CollectSettingsStore {
  _MemoryCollectSettingsStore([this.settings = const CollectSettings()]);

  CollectSettings settings;

  @override
  Future<CollectSettings> load() async => settings;

  @override
  Future<void> save(CollectSettings settings) async {
    this.settings = settings;
  }
}

void main() {
  Future<void> openHomeScreen(
    WidgetTester tester, {
    Future<CardModel> Function() loadCardModel = _loadAtOnce,
    _MemoryCollectSettingsStore? collectSettingsStore,
  }) async {
    final store = collectSettingsStore ?? _MemoryCollectSettingsStore();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          loadCardModel: loadCardModel,
          openCollectSettingsStore: () => store,
        ),
      ),
    );
    await tester.pump();
  }

  Future<void> openAdvanced(WidgetTester tester) async {
    await tester.tap(find.text('Advanced'));
    await tester.pump();
  }

  Future<void> tapCollectSwitch(WidgetTester tester) async {
    final collectSwitch = find.widgetWithText(
      SwitchListTile,
      'Collect misread cards',
    );
    await tester.ensureVisible(collectSwitch);
    await tester.tap(collectSwitch);
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

    testWidgets('does not say the result of a game unless it is turned on', (
      tester,
    ) async {
      await openHomeScreen(tester);
      await tester.tap(find.text('Advanced'));
      await tester.pump();
      final resultSwitch = find.widgetWithText(
        SwitchListTile,
        'Say the result when a game is finished',
      );
      final wasOnAtFirst = tester.widget<SwitchListTile>(resultSwitch).value;

      await tester.tap(resultSwitch);
      await tester.pump();

      expect(wasOnAtFirst, isFalse);
      expect(tester.widget<SwitchListTile>(resultSwitch).value, isTrue);
    });

    testWidgets('does not collect misread cards unless it is turned on', (
      tester,
    ) async {
      await openHomeScreen(tester);
      await openAdvanced(tester);

      final collectSwitch = find.widgetWithText(
        SwitchListTile,
        'Collect misread cards',
      );
      expect(tester.widget<SwitchListTile>(collectSwitch).value, isFalse);
      expect(find.text('Server address'), findsNothing);
    });

    testWidgets('asks where to send to once collecting is turned on', (
      tester,
    ) async {
      await openHomeScreen(tester);
      await openAdvanced(tester);

      await tapCollectSwitch(tester);

      expect(find.text('Server address'), findsOneWidget);
      expect(find.text('Upload token'), findsOneWidget);
    });

    testWidgets('keeps the collect settings as they are typed', (tester) async {
      final store = _MemoryCollectSettingsStore();
      await openHomeScreen(tester, collectSettingsStore: store);
      await openAdvanced(tester);
      await tapCollectSwitch(tester);

      await tester.enterText(
        find.widgetWithText(TextField, 'Server address'),
        'https://inbox.example',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Upload token'),
        'an-upload-token',
      );

      expect(store.settings.isOn, isTrue);
      expect(store.settings.server, 'https://inbox.example');
      expect(store.settings.token, 'an-upload-token');
    });

    testWidgets('shows the collect settings that were kept from before', (
      tester,
    ) async {
      final store = _MemoryCollectSettingsStore(
        const CollectSettings(
          isOn: true,
          server: 'https://inbox.example',
          token: 'an-upload-token',
        ),
      );
      await openHomeScreen(tester, collectSettingsStore: store);

      await openAdvanced(tester);

      expect(find.text('https://inbox.example'), findsOneWidget);
    });

    testWidgets('refuses a server address that is not https', (tester) async {
      await openHomeScreen(tester);
      await openAdvanced(tester);
      await tapCollectSwitch(tester);

      await tester.enterText(
        find.widgetWithText(TextField, 'Server address'),
        'http://inbox.example',
      );
      await tester.pump();

      expect(find.text('The address must start with https://'), findsOneWidget);
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
