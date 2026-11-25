import 'dart:async';

import 'package:flutter/material.dart';

import 'card_camera_view.dart';
import 'card_overlay.dart';
import 'cards.dart';
import 'guessing.dart';
import 'overlay_panel.dart';
import 'result_board.dart';
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

/// The guessing game: swipe anywhere to answer, double-tap to lock in.
class GameScreen extends StatefulWidget {
  const GameScreen({super.key, required this.cardCount});

  final int cardCount;

  @override
  State<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends State<GameScreen> {
  final GlobalKey<CardCameraViewState> _cameraView = GlobalKey();
  final TtsSpeaker _speaker = TtsSpeaker();

  /// Starts when the detector is loaded, as its config holds the spoken ranks.
  GuessingSession? _session;
  Offset _swipe = Offset.zero;
  bool _hasEndedEarly = false;

  void _say(String phrase) => unawaited(_speaker.say(phrase));

  void _onModelLoaded(ModelConfig config) {
    _session ??= GuessingSession(
      cardCount: widget.cardCount,
      say: _say,
      spokenRanks: config.spokenRanks,
    );
  }

  void _onCards(List<RecognizedCard> cards, int latencyMs) {
    setState(() {
      _session?.observe(cards);
    });
  }

  void _onSwipeEnd(DragEndDetails details) {
    final outcome = swipeOutcome(_swipe);
    if (outcome == null) return;
    setState(() {
      _session?.giveAnswer(outcome);
    });
  }

  void _lockIn() {
    setState(() {
      _session?.lockIn();
    });
  }

  void _endEarly() {
    final hasRounds = _session?.rounds.isNotEmpty ?? false;
    if (!hasRounds) {
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
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = _session;
    if (session != null && (session.isFinished || _hasEndedEarly)) {
      return Scaffold(
        body: ResultBoard(
          rounds: session.rounds,
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
        body: GestureDetector(
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
                onModelLoaded: _onModelLoaded,
                onCards: _onCards,
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [_buildRoundBanner(session), _buildSwipeHints()],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildRoundBanner(GuessingSession? session) {
    final card = session?.card;
    final roundNumber = (session?.rounds.length ?? 0) + 1;
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
                  'Answer: ${session?.answer?.phrase ?? '-'}',
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

  Widget _buildSwipeHints() {
    return const OverlayPanel(
      child: Text(
        'Swipe up: both right   left: color right\n'
        'Swipe right: rank right   down: miss\n'
        'Double-tap: lock in the answer',
        textAlign: TextAlign.center,
        style: TextStyle(color: Colors.white70, fontSize: 13),
      ),
    );
  }
}
