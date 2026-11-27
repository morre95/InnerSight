import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'card_camera_view.dart';
import 'card_overlay.dart';
import 'card_picture.dart';
import 'cards.dart';
import 'example_uploader.dart';
import 'frame_prep.dart';
import 'guessing.dart';
import 'overlay_panel.dart';
import 'recognition.dart';
import 'result_board.dart';
import 'round_collector.dart';
import 'tts_speaker.dart';

/// A drag shorter than this many logical pixels is not a swipe.
const double minSwipeDistance = 48;

/// The answer a swipe gives: up both right, left color right, right rank
/// right, down miss. Returns null when the drag is too short to be a swipe.
GuessOutcome? swipeOutcome(Offset swipe) {
  if (swipe.distance < minSwipeDistance) {
    return null;
  }
  if (swipe.dx.abs() > swipe.dy.abs()) {
    return swipe.dx < 0 ? GuessOutcome.colorRight : GuessOutcome.rankRight;
  }
  return swipe.dy < 0 ? GuessOutcome.bothRight : GuessOutcome.miss;
}

/// The guessing game accepts swipes and arrow keys for answers, and a
/// double-tap or Space to lock them in.
class GameScreen extends StatefulWidget {
  const GameScreen({
    super.key,
    required this.cardCount,
    required this.detector,
    required this.config,
    required this.minConfidence,
    required this.speaksResult,
    this.uploader,
  });

  final int cardCount;
  final CardDetector detector;
  final ModelConfig config;

  /// Detections below this confidence are ignored.
  final double minConfidence;

  /// Whether the voice says the count of every answer when the game ends.
  final bool speaksResult;

  /// Where the frames of misread cards are sent from the result board. Null
  /// when the misread cards are not collected.
  final ExampleUploader? uploader;

  @override
  State<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends State<GameScreen> {
  final GlobalKey<CardCameraViewState> _cameraView = GlobalKey();
  final TtsSpeaker _speaker = TtsSpeaker();

  late final GuessingSession _session;
  Offset _swipe = Offset.zero;
  bool _hasEndedEarly = false;

  /// The card of the round being played, cut from the frame it was last read
  /// in.
  CardPicture? _picture;

  /// The card of every locked round, so the player can check afterwards what
  /// the model read.
  final List<CardPicture> _pictures = [];

  /// The whole frame the card of the round being played was last read in.
  /// Kept only when the misread cards are collected, as it is far larger
  /// than the picture of the card.
  RoundFrame? _frame;

  /// Holds the frame of every locked round, when the misread cards are
  /// collected.
  RoundCollector? _collector;

  void _say(String phrase) => unawaited(_speaker.say(phrase));

  @override
  void initState() {
    super.initState();
    _session = GuessingSession(
      cardCount: widget.cardCount,
      say: _say,
      spokenRanks: widget.config.spokenRanks,
      speaksResult: widget.speaksResult,
    );
    final uploader = widget.uploader;
    if (uploader != null) {
      _collector = RoundCollector(uploader: uploader, config: widget.config);
    }
  }

  void _onCards(
    PreparedFrame frame,
    List<RecognizedCard> cards,
    int latencyMs,
  ) {
    setState(() {
      final roundCard = _session.observe(cards);
      if (roundCard != null) {
        _picture = cropCardPicture(
          frame.rgbBytes,
          frame.uprightWidth,
          roundCard.detection.box,
        );
        if (_collector != null) {
          _frame = RoundFrame(
            rgbBytes: frame.rgbBytes,
            width: frame.uprightWidth,
            height: frame.uprightHeight,
            card: roundCard,
          );
        }
      }
    });
  }

  void _onSwipeEnd(DragEndDetails details) {
    final outcome = swipeOutcome(_swipe);
    if (outcome != null) _giveAnswer(outcome);
  }

  void _giveAnswer(GuessOutcome outcome) {
    setState(() {
      _session.giveAnswer(outcome);
    });
  }

  KeyEventResult _onKeyEvent(FocusNode node, KeyEvent event) {
    final outcome = switch (event.logicalKey) {
      LogicalKeyboardKey.arrowUp => GuessOutcome.bothRight,
      LogicalKeyboardKey.arrowLeft => GuessOutcome.colorRight,
      LogicalKeyboardKey.arrowRight => GuessOutcome.rankRight,
      LogicalKeyboardKey.arrowDown => GuessOutcome.miss,
      _ => null,
    };
    final isLockIn = event.logicalKey == LogicalKeyboardKey.space;
    if (outcome == null && !isLockIn) return KeyEventResult.ignored;

    if (event is KeyDownEvent) {
      if (outcome != null) {
        _giveAnswer(outcome);
      } else {
        _lockIn();
      }
    }
    // Consume game keys, including repeats, so the browser doesn't scroll.
    return KeyEventResult.handled;
  }

  void _lockIn() {
    setState(() {
      final lockedRound = _session.lockIn();
      if (lockedRound != null) {
        // A round is only locked after its card was read, so it has a picture.
        _pictures.add(_picture!);
        _collector?.addRound(_frame!);
      }
    });
  }

  void _endEarly() {
    if (_session.rounds.isEmpty) {
      Navigator.of(context).pop();
      return;
    }
    unawaited(_speaker.stop());
    setState(() {
      _hasEndedEarly = true;
    });
  }

  @override
  void dispose() {
    unawaited(_speaker.dispose());
    _collector?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = _session;
    if (session.isFinished || _hasEndedEarly) {
      return Scaffold(
        body: ResultBoard(
          rounds: session.rounds,
          pictures: _pictures,
          collector: _collector,
          onDone: () => Navigator.of(context).pop(),
        ),
      );
    }
    // The system back gesture is a swipe from the screen edge, which a
    // blindfolded player makes by accident; only the close button leaves.
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Focus(
          autofocus: true,
          onKeyEvent: _onKeyEvent,
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onPanStart: (_) => _swipe = Offset.zero,
            onPanUpdate: (details) => _swipe += details.delta,
            onPanEnd: _onSwipeEnd,
            onDoubleTap: _lockIn,
            child: Stack(
              fit: StackFit.expand,
              children: [
                CardCameraView(
                  key: _cameraView,
                  detector: widget.detector,
                  config: widget.config,
                  minConfidence: widget.minConfidence,
                  preferredLensDirection: CameraLensDirection.front,
                  onCards: _onCards,
                ),
                SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _buildRoundBanner(session),
                        _buildControlHints(),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildRoundBanner(GuessingSession session) {
    final card = session.card;
    final roundNumber = session.rounds.length + 1;
    final cardText = card == null
        ? 'Hold up a card'
        : '${card.label} (${(card.detection.confidence * 100).round()}% sure)';
    return OverlayPanel(
      borderColor: card != null ? outlineColorFor(card.color) : Colors.white24,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Card $roundNumber of ${widget.cardCount}',
                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                ),
                Text(
                  cardText,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  'Answer: ${session.answer?.phrase ?? '-'}',
                  style: const TextStyle(color: Colors.white, fontSize: 15),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: () =>
                unawaited(_cameraView.currentState?.switchCamera()),
            icon: const Icon(Icons.cameraswitch),
            color: Colors.white70,
            tooltip: 'Switch camera',
          ),
          IconButton(
            onPressed: _endEarly,
            icon: const Icon(Icons.close),
            color: Colors.white70,
            tooltip: 'End the session',
          ),
        ],
      ),
    );
  }

  Widget _buildControlHints() {
    return const OverlayPanel(
      child: Text(
        kIsWeb
            ? 'Arrow keys or swipes\n'
                  '↑ Both right   ← Color right   → Rank right   ↓ Miss\n'
                  'Space or double-tap to lock in'
            : 'Swipe up: both right   left: color right\n'
                  'Swipe right: rank right   down: miss\n'
                  'Double-tap: lock in the answer',
        textAlign: TextAlign.center,
        style: TextStyle(color: Colors.white70, fontSize: 13),
      ),
    );
  }
}
