import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'card_overlay.dart';
import 'cards.dart';
import 'detector.dart';
import 'frame_prep.dart';
import 'recognition.dart';

const double defaultMinConfidence = 0.50;

/// Live camera preview that recognizes the cards in view and outlines them.
///
/// Owns the camera and the detector. Reports every recognized frame through
/// [onCards], so the screen around it decides what to do with the cards.
class CardCameraView extends StatefulWidget {
  const CardCameraView({
    super.key,
    required this.onCards,
    this.onModelLoaded,
    this.minConfidence = defaultMinConfidence,
  });

  /// Called for every recognized frame with its cards and how long it took.
  final void Function(
    PreparedFrame frame,
    List<RecognizedCard> cards,
    int latencyMs,
  )
  onCards;

  /// Called when the detector is loaded, before the first frame.
  final void Function(ModelConfig config)? onModelLoaded;

  /// Detections below this confidence are ignored.
  final double minConfidence;

  @override
  State<CardCameraView> createState() => CardCameraViewState();
}

class CardCameraViewState extends State<CardCameraView>
    with WidgetsBindingObserver {
  OnnxCardDetector? _detector;

  List<CameraDescription> _cameras = const [];
  int _selectedCameraIndex = 0;
  CameraController? _cameraController;
  Future<void> _cameraQueue = Future<void>.value();

  bool _isInitializing = true;
  bool _isProcessing = false;
  bool _suspendedForBackground = false;
  String? _errorMessage;

  List<RecognizedCard> _cards = const [];
  int _frameWidth = 1;
  int _frameHeight = 1;

  bool get hasSeveralCameras => _cameras.length > 1;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_bootstrap());
  }

  @override
  void didUpdateWidget(CardCameraView oldWidget) {
    super.didUpdateWidget(oldWidget);
    _detector?.minConfidence = widget.minConfidence;
  }

  /// Serializes camera open/switch/dispose calls so CameraX singleton state
  /// can never be mutated concurrently (e.g. during permission dialog resume).
  Future<void> _enqueueCameraOp(Future<void> Function() action) {
    final next = _cameraQueue.then((_) => action()).catchError((
      Object error,
      StackTrace stack,
    ) {
      debugPrint('Camera operation error: $error\n$stack');
    });
    _cameraQueue = next;
    return next;
  }

  List<CameraDescription> _selectPrimaryCameras(
    List<CameraDescription> allCameras,
  ) {
    CameraDescription? primaryBack;
    CameraDescription? primaryFront;
    for (final cam in allCameras) {
      if (cam.lensDirection == CameraLensDirection.back &&
          primaryBack == null) {
        primaryBack = cam;
      } else if (cam.lensDirection == CameraLensDirection.front &&
          primaryFront == null) {
        primaryFront = cam;
      }
    }
    final primary = <CameraDescription>[?primaryBack, ?primaryFront];
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
      final firstLine = rawMsg.isEmpty
          ? error.code
          : rawMsg.split('\n').first.trim();
      return 'Platform error: $firstLine';
    }
    return error.toString().split('\n').first.trim();
  }

  Future<void> _safeDisposeController(CameraController? controller) async {
    if (controller == null) return;
    try {
      if (controller.value.isInitialized &&
          controller.value.isStreamingImages) {
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
        final detector =
            _detector ??
            await OnnxCardDetector.fromAssets(
              minConfidence: widget.minConfidence,
            );
        _detector = detector;
        widget.onModelLoaded?.call(detector.config);

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
          _errorMessage =
              'Initialization failed: ${_compactErrorMessage(error)}';
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
      setState(() {
        _cards = recognized;
        _frameWidth = prepared.uprightWidth;
        _frameHeight = prepared.uprightHeight;
      });
      widget.onCards(prepared, recognized, stopwatch.elapsedMilliseconds);
    } catch (error) {
      debugPrint('Frame recognition error: $error');
    } finally {
      _isProcessing = false;
    }
  }

  Future<void> switchCamera() {
    if (_cameras.length < 2 || _isInitializing) {
      return Future<void>.value();
    }
    return _enqueueCameraOp(() async {
      if (!mounted || _cameras.length < 2) return;
      setState(() {
        _isInitializing = true;
        _cards = const [];
      });
      _selectedCameraIndex = (_selectedCameraIndex + 1) % _cameras.length;
      await _startCameraInternal(_cameras[_selectedCameraIndex]);
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
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
    if (_isInitializing ||
        controller == null ||
        !controller.value.isInitialized) {
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
}
