import 'dart:async';
import 'dart:typed_data';

import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:innersight_mobile/src/announcer.dart';
import 'package:innersight_mobile/src/card_camera_view.dart';
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/frame_prep.dart';
import 'package:innersight_mobile/src/game_screen.dart';
import 'package:innersight_mobile/src/recognition.dart';

const _backCamera = CameraDescription(
  name: 'back',
  lensDirection: CameraLensDirection.back,
  sensorOrientation: 90,
);
const _frontCamera = CameraDescription(
  name: 'front',
  lensDirection: CameraLensDirection.front,
  sensorOrientation: 270,
);

/// Stands in for the cameras of the phone. It keeps track of which cameras
/// are open, and never sends a frame.
class _FakeCameraPlatform extends CameraPlatform {
  _FakeCameraPlatform(this.cameras);

  final List<CameraDescription> cameras;

  /// The name of every camera that is open now, by its id.
  final Map<int, String> openCameras = {};

  /// The name of every camera that was opened, in the order they were.
  final List<String> opened = [];

  /// The most cameras that were open at the same time.
  int mostOpenAtOnce = 0;

  final Map<int, StreamController<CameraInitializedEvent>> _initialized = {};

  @override
  Future<List<CameraDescription>> availableCameras() async => cameras;

  @override
  Future<int> createCameraWithSettings(
    CameraDescription cameraDescription,
    MediaSettings? mediaSettings,
  ) async {
    final cameraId = opened.length;
    opened.add(cameraDescription.name);
    openCameras[cameraId] = cameraDescription.name;
    if (openCameras.length > mostOpenAtOnce) {
      mostOpenAtOnce = openCameras.length;
    }
    _initialized[cameraId] = StreamController.broadcast();
    return cameraId;
  }

  @override
  Stream<CameraInitializedEvent> onCameraInitialized(int cameraId) =>
      _initialized[cameraId]!.stream;

  @override
  Stream<CameraErrorEvent> onCameraError(int cameraId) =>
      StreamController<CameraErrorEvent>().stream;

  @override
  Stream<DeviceOrientationChangedEvent> onDeviceOrientationChanged() =>
      const Stream.empty();

  @override
  Future<void> initializeCamera(
    int cameraId, {
    ImageFormatGroup imageFormatGroup = ImageFormatGroup.unknown,
  }) async {
    _initialized[cameraId]!.add(
      CameraInitializedEvent(
        cameraId,
        480,
        640,
        ExposureMode.auto,
        false,
        FocusMode.auto,
        false,
      ),
    );
  }

  @override
  bool supportsImageStreaming() => true;

  @override
  Stream<CameraImageData> onStreamedFrameAvailable(
    int cameraId, {
    CameraImageStreamOptions? options,
  }) => StreamController<CameraImageData>().stream;

  @override
  Widget buildPreview(int cameraId) => const SizedBox.expand();

  @override
  Future<void> dispose(int cameraId) async {
    openCameras.remove(cameraId);
  }
}

class _NeverCalledDetector implements CardDetector {
  @override
  Future<List<Detection>> detect(
    PreparedFrame frame, {
    required double minConfidence,
  }) async => const [];
}

void main() {
  final cameraView = GlobalKey<CardCameraViewState>();

  Future<_FakeCameraPlatform> openScreen(
    WidgetTester tester,
    Widget screen, {
    List<CameraDescription> cameras = const [_backCamera, _frontCamera],
  }) async {
    final platform = _FakeCameraPlatform(cameras);
    CameraPlatform.instance = platform;
    addTearDown(
      () => tester.binding.handleAppLifecycleStateChanged(
        AppLifecycleState.resumed,
      ),
    );
    await tester.pumpWidget(MaterialApp(home: screen));
    await _letCameraWorkFinish(tester);
    return platform;
  }

  Future<_FakeCameraPlatform> openView(
    WidgetTester tester, {
    List<CameraDescription> cameras = const [_backCamera, _frontCamera],
  }) => openScreen(
    tester,
    CardCameraView(
      key: cameraView,
      detector: _NeverCalledDetector(),
      config: ModelConfig.defaults(),
      minConfidence: 0.5,
      onCards: (frame, cards, latencyMs) {},
    ),
    cameras: cameras,
  );

  Future<_FakeCameraPlatform> openGame(
    WidgetTester tester,
    List<CameraDescription> cameras,
  ) {
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      const MethodChannel('flutter_tts'),
      (_) async => null,
    );
    return openScreen(
      tester,
      GameScreen(
        cardCount: 10,
        detector: _NeverCalledDetector(),
        config: ModelConfig.defaults(),
        minConfidence: 0.5,
        speaksResult: false,
      ),
      cameras: cameras,
    );
  }

  group('GameScreen', () {
    testWidgets('starts on the front camera and can switch to the back', (
      tester,
    ) async {
      final platform = await openGame(tester, [_backCamera, _frontCamera]);

      expect(platform.opened, ['front']);

      await tester.tap(find.byTooltip('Switch camera'));
      await tester.pump(kDoubleTapTimeout);
      await _letCameraWorkFinish(tester);

      expect(platform.openCameras.values, ['back']);
    });

    testWidgets('starts on the back camera when there is no front camera', (
      tester,
    ) async {
      final platform = await openGame(tester, [_backCamera]);

      expect(platform.openCameras.values, ['back']);
    });

    testWidgets('arrow keys answer and Space locks in the round', (
      tester,
    ) async {
      await openGame(tester, [_frontCamera]);
      final view = tester.widget<CardCameraView>(find.byType(CardCameraView));
      final frame = PreparedFrame(
        rgbBytes: Uint8List.fromList([255, 0, 0]),
        uprightWidth: 1,
        uprightHeight: 1,
        inputTensor: Float32List(3),
        inputSize: 1,
        letterboxScale: 1,
        padLeft: 0,
        padTop: 0,
      );
      const card = RecognizedCard(
        detection: Detection(
          rank: '7',
          confidence: 0.9,
          box: Box(x1: 0, y1: 0, x2: 1, y2: 1),
        ),
        color: CardColor.red,
      );
      for (var i = 0; i < stableFrameCount; i++) {
        view.onCards(frame, [card], 0);
      }
      await tester.pump();

      const answers = [
        (LogicalKeyboardKey.arrowUp, 'both right'),
        (LogicalKeyboardKey.arrowLeft, 'color right'),
        (LogicalKeyboardKey.arrowRight, 'rank right'),
        (LogicalKeyboardKey.arrowDown, 'miss'),
      ];
      for (final (key, answer) in answers) {
        await tester.sendKeyEvent(key);
        await tester.pump();
        expect(find.text('Answer: $answer'), findsOneWidget);
      }

      await tester.sendKeyEvent(LogicalKeyboardKey.space);
      await tester.pump();

      expect(find.text('Card 2 of 10'), findsOneWidget);
      expect(find.text('Answer: -'), findsOneWidget);
    });
  });

  group('CardCameraView', () {
    testWidgets('opens the back camera first', (tester) async {
      final platform = await openView(tester);

      expect(platform.openCameras.values, ['back']);
    });

    testWidgets('keeps the camera open while the app is inactive', (
      tester,
    ) async {
      final platform = await openView(tester);

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      await _letCameraWorkFinish(tester);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await _letCameraWorkFinish(tester);

      expect(platform.opened, ['back']);
      expect(platform.openCameras.values, ['back']);
    });

    testWidgets('closes the camera when the app is paused', (tester) async {
      final platform = await openView(tester);

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await _letCameraWorkFinish(tester);

      expect(platform.openCameras, isEmpty);
    });

    testWidgets('opens the same camera again when the app is resumed', (
      tester,
    ) async {
      final platform = await openView(tester);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await _letCameraWorkFinish(tester);

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await _letCameraWorkFinish(tester);

      expect(platform.opened, ['back', 'back']);
      expect(platform.openCameras.values, ['back']);
    });

    testWidgets('switches to the other camera', (tester) async {
      final platform = await openView(tester);

      unawaited(cameraView.currentState!.switchCamera());
      await _letCameraWorkFinish(tester);

      expect(platform.openCameras.values, ['front']);
    });

    testWidgets('never has two cameras open when it is paused, resumed and '
        'switched at once', (tester) async {
      final platform = await openView(tester);

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      unawaited(cameraView.currentState!.switchCamera());
      await _letCameraWorkFinish(tester);

      expect(platform.mostOpenAtOnce, 1);
      expect(platform.openCameras.values, ['front']);
    });

    testWidgets('offers to try again when the phone has no camera', (
      tester,
    ) async {
      await openView(tester, cameras: const []);

      expect(find.text('No cameras found on this device.'), findsOneWidget);
      expect(find.text('Retry Camera'), findsOneWidget);
    });
  });
}

/// Camera calls are queued and wait for a frame to be drawn in between, so a
/// few frames pass before they have all finished. Closing a camera also waits
/// for the real event loop, which the fake clock of a widget test never runs.
Future<void> _letCameraWorkFinish(WidgetTester tester) async {
  for (var frame = 0; frame < 10; frame++) {
    await tester.pump(const Duration(milliseconds: 20));
    await tester.runAsync(() => Future<void>.delayed(Duration.zero));
  }
}
