import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'announcer.dart';
import 'cards.dart';
import 'detector.dart';
import 'frame_prep.dart';
import 'recognition.dart';
import 'tts_speaker.dart';

/// Outline colors matching `OUTLINE_BGR` in `src/innersight/annotation.py`.
Color outlineColorFor(CardColor color) {
  return switch (color) {
    CardColor.red => const Color(0xFFFF1744),
    CardColor.yellow => const Color(0xFFFFEA00),
    CardColor.green => const Color(0xFF00C853),
    CardColor.blue => const Color(0xFF2979FF),
    CardColor.wild => const Color(0xFFFF00FF),
    CardColor.back => const Color(0xFFFFFFFF),
  };
}

class CameraRecognitionScreen extends StatefulWidget {
  const CameraRecognitionScreen({super.key});

  @override
  State<CameraRecognitionScreen> createState() =>
      _CameraRecognitionScreenState();
}

class _CameraRecognitionScreenState extends State<CameraRecognitionScreen>
    with WidgetsBindingObserver {
  final TtsSpeaker _speaker = TtsSpeaker();
  late CardAnnouncer _announcer;
  OnnxCardDetector? _detector;

  List<CameraDescription> _cameras = const [];
  int _selectedCameraIndex = 0;
  CameraController? _cameraController;
  Future<void> _cameraQueue = Future<void>.value();

  bool _isInitializing = true;
  bool _isProcessing = false;
  bool _suspendedForBackground = false;
  String? _errorMessage;

  double _minConfidence = 0.50;
  List<RecognizedCard> _cards = const [];
  int _frameWidth = 1;
  int _frameHeight = 1;
  int? _latencyMs;
  String? _lastSpokenPhrase;
  CardColor? _lastSpokenColor;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _announcer = CardAnnouncer(say: _onAnnounce);
    unawaited(_bootstrap());
  }

  /// Serializes camera open/switch/dispose calls so CameraX singleton state
  /// can never be mutated concurrently (e.g. during permission dialog resume).
  Future<void> _enqueueCameraOp(Future<void> Function() action) {
    final next = _cameraQueue.then((_) => action()).catchError((Object error, StackTrace stack) {
      debugPrint('Camera operation error: $error\n$stack');
    });
    _cameraQueue = next;
    return next;
  }

  void _onAnnounce(String phrase) {
    unawaited(_speaker.say(phrase));
    if (!mounted) return;
    setState(() {
      _lastSpokenPhrase = phrase;
      _lastSpokenColor = _announcer.announced?.color;
    });
  }

  List<CameraDescription> _selectPrimaryCameras(List<CameraDescription> allCameras) {
    CameraDescription? primaryBack;
    CameraDescription? primaryFront;
    for (final cam in allCameras) {
      if (cam.lensDirection == CameraLensDirection.back && primaryBack == null) {
        primaryBack = cam;
      } else if (cam.lensDirection == CameraLensDirection.front && primaryFront == null) {
        primaryFront = cam;
      }
    }
    final primary = <CameraDescription>[
      ?primaryBack,
      ?primaryFront,
    ];
    return primary.isNotEmpty ? primary : allCameras;
  }

  String _compactErrorMessage(Object error) {
    if (error is CameraException) {
      final rawDesc = (error.description ?? '').trim();
      final firstLine = rawDesc.isEmpty
          ? 'Please grant camera permission and try again.'
          : rawDesc.split('\n').first.trim();
      return 'Camera error (${error.code}): $firstLine';
    }
    if (error is PlatformException) {
      final rawMsg = (error.message ?? '').trim();
      final firstLine = rawMsg.isEmpty ? error.code : rawMsg.split('\n').first.trim();
      return 'Platform error: $firstLine';
    }
    return error.toString().split('\n').first.trim();
  }

  Future<void> _safeDisposeController(CameraController? controller) async {
    if (controller == null) return;
    try {
      if (controller.value.isInitialized && controller.value.isStreamingImages) {
        await controller.stopImageStream();
      }
    } catch (error) {
      debugPrint('Ignored stopImageStream error during dispose: $error');
    }
    try {
      await controller.dispose();
    } catch (error) {
      debugPrint('Ignored controller.dispose error: $error');
    }
  }

  Future<void> _bootstrap() {
    return _enqueueCameraOp(() async {
      if (!mounted) return;
      setState(() {
        _isInitializing = true;
        _errorMessage = null;
      });

      try {
        await _speaker.initialize();
        final detector =
            _detector ?? await OnnxCardDetector.fromAssets(minConfidence: _minConfidence);
        _detector = detector;
        _announcer = CardAnnouncer(
          say: _onAnnounce,
          spokenRanks: detector.config.spokenRanks,
        );

        final discovered = await availableCameras();
        if (discovered.isEmpty) {
          if (!mounted) return;
          setState(() {
            _errorMessage = 'No cameras found on this device.';
            _isInitializing = false;
          });
          return;
        }

        _cameras = _selectPrimaryCameras(discovered);
        _selectedCameraIndex = 0;

        await _startCameraInternal(_cameras[_selectedCameraIndex]);
      } catch (error, stack) {
        debugPrint('Bootstrap error: $error\n$stack');
        if (!mounted) return;
        setState(() {
          _errorMessage = 'Initialization failed: ${_compactErrorMessage(error)}';
          _isInitializing = false;
        });
      }
    });
  }

  Future<void> _startCameraInternal(CameraDescription description) async {
    final previous = _cameraController;
    if (previous != null) {
      if (mounted) {
        setState(() {
          _cameraController = null;
          _cards = const [];
        });
      } else {
        _cameraController = null;
      }
      await _safeDisposeController(previous);
    }

    final controller = CameraController(
      description,
      ResolutionPreset.medium,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.yuv420,
    );

    try {
      await controller.initialize();
      if (!mounted) {
        await _safeDisposeController(controller);
        return;
      }

      // Mount CameraPreview first so CameraX's Flutter surface producer attaches
      // cleanly before image analysis starts streaming.
      setState(() {
        _cameraController = controller;
        _cards = const [];
        _isInitializing = false;
        _errorMessage = null;
      });

      await WidgetsBinding.instance.endOfFrame;
      if (!mounted || _cameraController != controller) {
        return;
      }

      await controller.startImageStream(_onCameraFrame);
    } catch (error, stack) {
      debugPrint('Start camera error: $error\n$stack');
      if (_cameraController == controller) {
        _cameraController = null;
      }
      await _safeDisposeController(controller);
      if (!mounted) return;
      setState(() {
        _errorMessage = _compactErrorMessage(error);
        _isInitializing = false;
      });
    }
  }

  void _onCameraFrame(CameraImage image) {
    final detector = _detector;
    final controller = _cameraController;
    if (_isProcessing || detector == null || controller == null || !mounted) {
      return;
    }

    _isProcessing = true;
    final sensorOrientation = controller.description.sensorOrientation;
    unawaited(_processFrame(image, detector, sensorOrientation));
  }

  Future<void> _processFrame(
    CameraImage image,
    OnnxCardDetector detector,
    int sensorOrientation,
  ) async {
    final stopwatch = Stopwatch()..start();
    try {
      final prepared = await prepareCameraFrame(
        image,
        sensorOrientation: sensorOrientation,
        inputSize: detector.config.inputSize,
      );
      final recognized = await recognizeCards(
        prepared,
        detector,
        detector.config,
      );
      stopwatch.stop();

      if (!mounted || _cameraController == null) return;
      _announcer.observe(recognized);

      setState(() {
        _cards = recognized;
        _frameWidth = prepared.uprightWidth;
        _frameHeight = prepared.uprightHeight;
        _latencyMs = stopwatch.elapsedMilliseconds;
      });
    } catch (error) {
      debugPrint('Frame recognition error: $error');
    } finally {
      _isProcessing = false;
    }
  }

  Future<void> _switchCamera() {
    if (_cameras.length < 2 || _isInitializing) {
      return Future<void>.value();
    }
    return _enqueueCameraOp(() async {
      if (!mounted || _cameras.length < 2) return;
      setState(() {
        _isInitializing = true;
        _cards = const [];
      });
      _announcer.reset();
      _selectedCameraIndex = (_selectedCameraIndex + 1) % _cameras.length;
      await _startCameraInternal(_cameras[_selectedCameraIndex]);
    });
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
      _detector?.minConfidence = value;
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Only suspend on full background (`paused`), NOT `inactive` (which fires
    // when Android displays the runtime Camera Permission dialog).
    if (state == AppLifecycleState.paused) {
      if (_cameraController != null) {
        _suspendedForBackground = true;
        unawaited(
          _enqueueCameraOp(() async {
            final active = _cameraController;
            _cameraController = null;
            await _safeDisposeController(active);
          }),
        );
      }
    } else if (state == AppLifecycleState.resumed) {
      if (_suspendedForBackground && _cameras.isNotEmpty) {
        _suspendedForBackground = false;
        unawaited(
          _enqueueCameraOp(() async {
            if (!mounted) return;
            setState(() {
              _isInitializing = true;
            });
            await _startCameraInternal(_cameras[_selectedCameraIndex]);
          }),
        );
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    final controller = _cameraController;
    _cameraController = null;
    unawaited(_safeDisposeController(controller));
    unawaited(_detector?.dispose());
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
          _buildPreviewArea(),
          SafeArea(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _buildTopBanner(),
                _buildBottomControls(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPreviewArea() {
    if (_errorMessage != null) {
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(28, 88, 28, 148),
          child: Center(
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.videocam_off_outlined,
                    color: Colors.white70,
                    size: 52,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _errorMessage!,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 15),
                  ),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: _bootstrap,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry Camera'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    final controller = _cameraController;
    if (_isInitializing || controller == null || !controller.value.isInitialized) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: Colors.white),
            SizedBox(height: 16),
            Text(
              'Loading YOLO v0.1.0 model & camera...',
              style: TextStyle(color: Colors.white70),
            ),
          ],
        ),
      );
    }

    final isFrontCamera =
        controller.description.lensDirection == CameraLensDirection.front;

    return Center(
      child: CameraPreview(
        controller,
        child: CustomPaint(
          painter: CardOverlayPainter(
            cards: _cards,
            frameWidth: _frameWidth,
            frameHeight: _frameHeight,
            mirrorHorizontal: isFrontCamera,
          ),
        ),
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
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.72),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: activeFace != null
                ? outlineColorFor(activeFace.color)
                : Colors.white24,
            width: 1.5,
          ),
        ),
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
                padding: const EdgeInsets.symmetric(
                  horizontal: 8,
                  vertical: 4,
                ),
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
                  onPressed: _cameras.length > 1 ? _switchCamera : null,
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

/// Paints bounding boxes and labels for recognized cards on top of [CameraPreview].
class CardOverlayPainter extends CustomPainter {
  const CardOverlayPainter({
    required this.cards,
    required this.frameWidth,
    required this.frameHeight,
    this.mirrorHorizontal = false,
  });

  final List<RecognizedCard> cards;
  final int frameWidth;
  final int frameHeight;
  final bool mirrorHorizontal;

  @override
  void paint(Canvas canvas, Size size) {
    if (cards.isEmpty || frameWidth <= 0 || frameHeight <= 0) {
      return;
    }

    final scaleX = size.width / frameWidth;
    final scaleY = size.height / frameHeight;

    for (final card in cards) {
      final box = card.detection.box;
      final rawLeft = mirrorHorizontal
          ? (frameWidth - box.x2).toDouble()
          : box.x1.toDouble();
      final rawRight = mirrorHorizontal
          ? (frameWidth - box.x1).toDouble()
          : box.x2.toDouble();

      final rect = Rect.fromLTRB(
        rawLeft * scaleX,
        box.y1 * scaleY,
        rawRight * scaleX,
        box.y2 * scaleY,
      );

      final color = outlineColorFor(card.color);
      final boxPaint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3.0;
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(6)),
        boxPaint,
      );

      final confPct = (card.detection.confidence * 100).round();
      final textSpan = TextSpan(
        text: '${card.label} $confPct%',
        style: TextStyle(
          color: color,
          fontSize: 14,
          fontWeight: FontWeight.w700,
        ),
      );
      final textPainter = TextPainter(
        text: textSpan,
        textDirection: TextDirection.ltr,
      )..layout();

      const pillPaddingH = 8.0;
      const pillPaddingV = 4.0;
      final pillWidth = textPainter.width + pillPaddingH * 2;
      final pillHeight = textPainter.height + pillPaddingV * 2;
      final pillLeft = rect.left.clamp(
        0.0,
        (size.width - pillWidth).clamp(0.0, size.width),
      );
      final pillTop = rect.top - pillHeight - 4 >= 0
          ? rect.top - pillHeight - 4
          : rect.top + 4;

      final pillRect = RRect.fromRectAndRadius(
        Rect.fromLTWH(pillLeft, pillTop, pillWidth, pillHeight),
        const Radius.circular(6),
      );
      canvas.drawRRect(
        pillRect,
        Paint()..color = Colors.black.withValues(alpha: 0.78),
      );
      textPainter.paint(
        canvas,
        Offset(pillLeft + pillPaddingH, pillTop + pillPaddingV),
      );
    }
  }

  @override
  bool shouldRepaint(covariant CardOverlayPainter oldDelegate) {
    return oldDelegate.cards != cards ||
        oldDelegate.frameWidth != frameWidth ||
        oldDelegate.frameHeight != frameHeight ||
        oldDelegate.mirrorHorizontal != mirrorHorizontal;
  }
}
