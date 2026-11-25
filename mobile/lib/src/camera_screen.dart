import 'dart:async';

import 'package:flutter/material.dart';

import 'announcer.dart';
import 'card_camera_view.dart';
import 'card_overlay.dart';
import 'cards.dart';
import 'overlay_panel.dart';
import 'tts_speaker.dart';

/// Reads every card held up to the camera aloud.
class CameraRecognitionScreen extends StatefulWidget {
  const CameraRecognitionScreen({super.key});

  @override
  State<CameraRecognitionScreen> createState() =>
      _CameraRecognitionScreenState();
}

class _CameraRecognitionScreenState extends State<CameraRecognitionScreen> {
  final GlobalKey<CardCameraViewState> _cameraView = GlobalKey();
  final TtsSpeaker _speaker = TtsSpeaker();
  late CardAnnouncer _announcer;

  double _minConfidence = defaultMinConfidence;
  int? _latencyMs;
  String? _lastSpokenPhrase;
  CardColor? _lastSpokenColor;

  @override
  void initState() {
    super.initState();
    _announcer = CardAnnouncer(say: _onAnnounce);
  }

  void _onAnnounce(String phrase) {
    unawaited(_speaker.say(phrase));
    if (!mounted) return;
    setState(() {
      _lastSpokenPhrase = phrase;
      _lastSpokenColor = _announcer.announced?.color;
    });
  }

  void _onModelLoaded(ModelConfig config) {
    _announcer = CardAnnouncer(
      say: _onAnnounce,
      spokenRanks: config.spokenRanks,
    );
  }

  void _onCards(List<RecognizedCard> cards, int latencyMs) {
    _announcer.observe(cards);
    setState(() {
      _latencyMs = latencyMs;
    });
  }

  void _switchCamera() {
    _announcer.reset();
    unawaited(_cameraView.currentState?.switchCamera());
  }

  void _toggleMute() {
    setState(() {
      _speaker.isMuted = !_speaker.isMuted;
    });
    if (_speaker.isMuted) {
      unawaited(_speaker.stop());
    }
  }

  void _onConfidenceChanged(double value) {
    setState(() {
      _minConfidence = value;
    });
  }

  @override
  void dispose() {
    unawaited(_speaker.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          CardCameraView(
            key: _cameraView,
            minConfidence: _minConfidence,
            onModelLoaded: _onModelLoaded,
            onCards: _onCards,
          ),
          SafeArea(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [_buildTopBanner(), _buildBottomControls()],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopBanner() {
    final activeFace = _announcer.announced;
    final bannerText = _lastSpokenPhrase ?? 'Hold a UNO card in view';
    final dotColor = _lastSpokenColor != null
        ? outlineColorFor(_lastSpokenColor!)
        : Colors.white38;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: OverlayPanel(
        borderColor: activeFace != null
            ? outlineColorFor(activeFace.color)
            : Colors.white24,
        child: Row(
          children: [
            Container(
              width: 14,
              height: 14,
              decoration: BoxDecoration(
                color: dotColor,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                bannerText,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (_latencyMs != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white12,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '${_latencyMs}ms',
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 12,
                    fontFeatures: [FontFeature.tabularFigures()],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildBottomControls() {
    final confPercent = (_minConfidence * 100).round();
    final hasSeveralCameras =
        _cameraView.currentState?.hasSeveralCameras ?? false;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.75),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.white12),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                const Icon(Icons.tune, color: Colors.white70, size: 18),
                const SizedBox(width: 8),
                Text(
                  'Conf $confPercent%',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Expanded(
                  child: Slider(
                    value: _minConfidence,
                    min: 0.20,
                    max: 0.90,
                    divisions: 14,
                    onChanged: _onConfidenceChanged,
                  ),
                ),
              ],
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                FilledButton.tonalIcon(
                  onPressed: _toggleMute,
                  icon: Icon(
                    _speaker.isMuted ? Icons.volume_off : Icons.volume_up,
                  ),
                  label: Text(_speaker.isMuted ? 'Muted' : 'Voice On'),
                ),
                FilledButton.tonalIcon(
                  onPressed: hasSeveralCameras ? _switchCamera : null,
                  icon: const Icon(Icons.cameraswitch),
                  label: const Text('Switch Cam'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
