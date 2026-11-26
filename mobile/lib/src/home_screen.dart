import 'dart:async';

import 'package:flutter/material.dart';

import 'camera_screen.dart';
import 'cards.dart';
import 'detector.dart';
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
  const HomeScreen({super.key, this.loadCardModel = loadPackedCardModel});

  /// Loads the model once, when the app starts.
  final Future<CardModel> Function() loadCardModel;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _cardCount = defaultCardCount;

  double _minConfidence = defaultMinConfidence;
  bool _showsAdvanced = false;

  /// Loaded once and kept for as long as the app runs, as loading is slow.
  CardModel? _cardModel;
  String? _loadError;

  @override
  void initState() {
    super.initState();
    unawaited(_loadCardModel());
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
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
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

  /// What most players never need: how sure the model must be of a card, and
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
