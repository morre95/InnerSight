import 'dart:async';

import 'package:flutter/material.dart';

import 'camera_screen.dart';
import 'cards.dart';
import 'collect_settings.dart';
import 'collect_settings_fields.dart';
import 'detector.dart';
import 'example_uploader.dart';
import 'game_screen.dart';
import 'recognition.dart';
import 'tts_speaker.dart';

const int defaultCardCount = 10;
const int maxCardCount = 50;

const double defaultMinConfidence = 0.50;
const double lowestMinConfidence = 0.20;
const double highestMinConfidence = 0.90;

/// The detector that finds the cards, and the ranks and wording of its model.
typedef CardModel = ({CardDetector detector, ModelConfig config});

/// Loads the model that is packed with the app.
Future<CardModel> loadPackedCardModel() async {
  final detector = await OnnxCardDetector.fromAssets();
  return (detector: detector, config: detector.config);
}

/// Where a session is set up: choose how many cards to guess, then start.
class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    this.loadCardModel = loadPackedCardModel,
    this.openCollectSettingsStore = PreferencesCollectSettingsStore.new,
  });

  /// Loads the model once, when the app starts.
  final Future<CardModel> Function() loadCardModel;

  /// Opens what keeps the collect settings until the app is started again.
  final CollectSettingsStore Function() openCollectSettingsStore;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _cardCount = defaultCardCount;

  double _minConfidence = defaultMinConfidence;
  bool _speaksResult = false;
  bool _showsAdvanced = false;

  late final CollectSettingsStore _collectSettingsStore = widget
      .openCollectSettingsStore();

  /// Null until the settings are read from where they are kept.
  CollectSettings? _collectSettings;

  /// Loaded once and kept for as long as the app runs, as loading is slow.
  CardModel? _cardModel;
  String? _loadError;

  @override
  void initState() {
    super.initState();
    unawaited(_loadCardModel());
    unawaited(_loadCollectSettings());
  }

  Future<void> _loadCollectSettings() async {
    CollectSettings settings;
    try {
      settings = await _collectSettingsStore.load();
    } catch (error, stack) {
      // Without the saved settings, collecting starts turned off.
      debugPrint('Collect settings load error: $error\n$stack');
      settings = const CollectSettings();
    }
    if (!mounted) return;
    setState(() {
      _collectSettings = settings;
    });
  }

  Future<void> _changeCollectSettings(CollectSettings settings) async {
    setState(() {
      _collectSettings = settings;
    });
    try {
      await _collectSettingsStore.save(settings);
    } catch (error, stack) {
      debugPrint('Collect settings save error: $error\n$stack');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('The collect settings could not be saved.'),
        ),
      );
    }
  }

  /// Where the frames of misread cards are sent, or null when they are not
  /// collected.
  ExampleUploader? _createUploader() {
    final settings = _collectSettings;
    if (settings == null || !settings.isReady) return null;
    return HttpExampleUploader(
      server: settings.serverUri!,
      token: settings.token.trim(),
    );
  }

  Future<void> _loadCardModel() async {
    setState(() {
      _loadError = null;
    });
    try {
      final cardModel = await widget.loadCardModel();
      if (!mounted) return;
      setState(() {
        _cardModel = cardModel;
      });
    } catch (error, stack) {
      debugPrint('Card model load error: $error\n$stack');
      if (!mounted) return;
      setState(() {
        _loadError = 'The card model could not be loaded.';
      });
    }
  }

  void _open(Widget screen) {
    TtsSpeaker.enableBrowserAudio();
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen));
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      body: SafeArea(
        // Scrolls, as the advanced settings and the keyboard together need
        // more room than a phone has.
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'InnerSight',
                  textAlign: TextAlign.center,
                  style: textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Guess the card you hold while blindfolded. The voice reads '
                  'the card; swipe to say how your guess went, and double-tap '
                  'to lock it in.',
                  textAlign: TextAlign.center,
                  style: textTheme.bodyMedium,
                ),
                const SizedBox(height: 32),
                Text(
                  '$_cardCount cards',
                  textAlign: TextAlign.center,
                  style: textTheme.titleLarge,
                ),
                Slider(
                  value: _cardCount.toDouble(),
                  min: 1,
                  max: maxCardCount.toDouble(),
                  divisions: maxCardCount - 1,
                  label: '$_cardCount',
                  onChanged: (value) => setState(() {
                    _cardCount = value.round();
                  }),
                ),
                const SizedBox(height: 16),
                ..._buildStartControls(textTheme),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// The buttons that open a screen, or what stands in for them while the
  /// model is loading or could not be loaded.
  List<Widget> _buildStartControls(TextTheme textTheme) {
    final cardModel = _cardModel;
    if (cardModel != null) {
      return [
        FilledButton.icon(
          onPressed: () => _open(
            GameScreen(
              cardCount: _cardCount,
              detector: cardModel.detector,
              config: cardModel.config,
              minConfidence: _minConfidence,
              speaksResult: _speaksResult,
              uploader: _createUploader(),
            ),
          ),
          icon: const Icon(Icons.play_arrow),
          label: const Text('Start game'),
        ),
        const SizedBox(height: 12),
        TextButton.icon(
          onPressed: () => setState(() {
            _showsAdvanced = !_showsAdvanced;
          }),
          icon: Icon(_showsAdvanced ? Icons.expand_less : Icons.expand_more),
          label: const Text('Advanced'),
        ),
        if (_showsAdvanced) ..._buildAdvancedControls(textTheme, cardModel),
      ];
    }
    if (_loadError != null) {
      return [
        Text(
          _loadError!,
          textAlign: TextAlign.center,
          style: textTheme.bodyMedium,
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: _loadCardModel,
          icon: const Icon(Icons.refresh),
          label: const Text('Try again'),
        ),
      ];
    }
    return [
      const Center(child: CircularProgressIndicator()),
      const SizedBox(height: 12),
      Text(
        'Loading the card model...',
        textAlign: TextAlign.center,
        style: textTheme.bodyMedium,
      ),
    ];
  }

  /// What most players never need: how sure the model must be of a card,
  /// saying the result when a game ends, collecting the misread cards, and
  /// reading cards aloud without a game.
  List<Widget> _buildAdvancedControls(
    TextTheme textTheme,
    CardModel cardModel,
  ) {
    return [
      Text(
        'Read a card when ${(_minConfidence * 100).round()}% sure',
        textAlign: TextAlign.center,
        style: textTheme.bodyMedium,
      ),
      Slider(
        value: _minConfidence,
        min: lowestMinConfidence,
        max: highestMinConfidence,
        divisions: 14,
        onChanged: (value) => setState(() {
          _minConfidence = value;
        }),
      ),
      SwitchListTile(
        title: const Text('Say the result when a game is finished'),
        value: _speaksResult,
        onChanged: (value) => setState(() {
          _speaksResult = value;
        }),
      ),
      if (_collectSettings case final collectSettings?)
        CollectSettingsFields(
          settings: collectSettings,
          onChanged: _changeCollectSettings,
        ),
      FilledButton.tonalIcon(
        onPressed: () => _open(
          CameraRecognitionScreen(
            detector: cardModel.detector,
            config: cardModel.config,
            minConfidence: _minConfidence,
          ),
        ),
        icon: const Icon(Icons.volume_up),
        label: const Text('Just read cards aloud'),
      ),
    ];
  }
}
