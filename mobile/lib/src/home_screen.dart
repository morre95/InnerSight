import 'dart:async';

import 'package:flutter/material.dart';

import 'camera_screen.dart';
import 'detector.dart';
import 'game_screen.dart';

const int defaultCardCount = 10;
const int maxCardCount = 50;

/// Where a session is set up: choose how many cards to guess, then start.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _cardCount = defaultCardCount;

  /// Loaded once and kept for as long as the app runs, as loading is slow.
  OnnxCardDetector? _detector;
  String? _loadError;

  @override
  void initState() {
    super.initState();
    unawaited(_loadDetector());
  }

  Future<void> _loadDetector() async {
    setState(() {
      _loadError = null;
    });
    try {
      final detector = await OnnxCardDetector.fromAssets();
      if (!mounted) return;
      setState(() {
        _detector = detector;
      });
    } catch (error, stack) {
      debugPrint('Detector load error: $error\n$stack');
      if (!mounted) return;
      setState(() {
        _loadError = 'The card model could not be loaded.';
      });
    }
  }

  void _open(Widget screen) {
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
  /// detector is loading or could not be loaded.
  List<Widget> _buildStartControls(TextTheme textTheme) {
    final detector = _detector;
    if (detector != null) {
      return [
        FilledButton.icon(
          onPressed: () => _open(
            GameScreen(
              cardCount: _cardCount,
              detector: detector,
              config: detector.config,
            ),
          ),
          icon: const Icon(Icons.play_arrow),
          label: const Text('Start game'),
        ),
        const SizedBox(height: 12),
        FilledButton.tonalIcon(
          onPressed: () => _open(
            CameraRecognitionScreen(
              detector: detector,
              config: detector.config,
            ),
          ),
          icon: const Icon(Icons.volume_up),
          label: const Text('Just read cards aloud'),
        ),
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
          onPressed: _loadDetector,
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
}
