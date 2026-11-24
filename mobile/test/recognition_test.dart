import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:innersight_mobile/src/announcer.dart';
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/color_classifier.dart';
import 'package:innersight_mobile/src/detector.dart';
import 'package:innersight_mobile/src/frame_prep.dart';
import 'package:innersight_mobile/src/recognition.dart';

class _FakeDetector implements CardDetector {
  _FakeDetector(this.detections);
  final List<Detection> detections;

  @override
  Future<List<Detection>> detect(PreparedFrame frame) async => detections;
}

Uint8List _solidRgb(int width, int height, int r, int g, int b) {
  final bytes = Uint8List(width * height * 3);
  for (var i = 0; i < bytes.length; i += 3) {
    bytes[i] = r;
    bytes[i + 1] = g;
    bytes[i + 2] = b;
  }
  return bytes;
}

RecognizedCard _makeCard(
  CardColor color,
  String rank, {
  double confidence = 0.9,
}) {
  return RecognizedCard(
    detection: Detection(
      rank: rank,
      confidence: confidence,
      box: const Box(x1: 0, y1: 0, x2: 10, y2: 10),
    ),
    color: color,
  );
}

void main() {
  group('ModelConfig & CardFace wording', () {
    test('loads exported model_config.json with valid ranks and spoken phrases', () {
      final raw = File('assets/models/model_config.json').readAsStringSync();
      final config = ModelConfig.fromJsonString(raw);

      expect(config.inputSize, 640);
      expect(config.ranks.length, greaterThanOrEqualTo(16));
      expect(config.ranks.first, '0');
      expect(config.ranks.contains('back'), isTrue);
      expect(config.ranks.every(config.spokenRanks.containsKey), isTrue);
    });

    test('formats labels and spoken names identically to Python', () {
      expect(
        spokenName(const CardFace(color: CardColor.red, rank: '7')),
        'red seven',
      );
      expect(
        spokenName(const CardFace(color: CardColor.blue, rank: '+2')),
        'blue draw two',
      );
      expect(
        spokenName(const CardFace(color: CardColor.wild, rank: 'wild')),
        'wild',
      );
      expect(
        spokenName(const CardFace(color: CardColor.wild, rank: '+4')),
        'wild draw four',
      );
      expect(
        spokenName(const CardFace(color: CardColor.wild, rank: 'joker')),
        'wild joker',
      );
      expect(
        spokenName(const CardFace(color: CardColor.back, rank: 'back')),
        'card back',
      );
    });
  });

  group('HSV color classification', () {
    test('classifies red at both low hue and wrap-around high hue', () {
      final lowHueRed = _solidRgb(40, 40, 225, 25, 10);
      final highHueRed = _solidRgb(40, 40, 230, 10, 80);

      expect(
        classifyCardColor(
          rgbBytes: lowHueRed,
          imageWidth: 40,
          imageHeight: 40,
        ),
        CardColor.red,
      );
      expect(
        classifyCardColor(
          rgbBytes: highHueRed,
          imageWidth: 40,
          imageHeight: 40,
        ),
        CardColor.red,
      );
    });

    test('classifies yellow, green, and blue cards', () {
      expect(
        classifyCardColor(
          rgbBytes: _solidRgb(40, 40, 235, 215, 10),
          imageWidth: 40,
          imageHeight: 40,
        ),
        CardColor.yellow,
      );
      expect(
        classifyCardColor(
          rgbBytes: _solidRgb(40, 40, 20, 190, 40),
          imageWidth: 40,
          imageHeight: 40,
        ),
        CardColor.green,
      );
      expect(
        classifyCardColor(
          rgbBytes: _solidRgb(40, 40, 20, 70, 225),
          imageWidth: 40,
          imageHeight: 40,
        ),
        CardColor.blue,
      );
    });

    test('falls back to wild on low-saturation or 4-way split crops', () {
      final washedOut = _solidRgb(40, 40, 235, 235, 235);
      expect(
        classifyCardColor(
          rgbBytes: washedOut,
          imageWidth: 40,
          imageHeight: 40,
        ),
        CardColor.wild,
      );

      final fourWay = Uint8List(40 * 40 * 3);
      for (var y = 0; y < 40; y++) {
        for (var x = 0; x < 40; x++) {
          final idx = (y * 40 + x) * 3;
          if (y < 20 && x < 20) {
            fourWay[idx] = 220;
          } else if (y < 20) {
            fourWay[idx] = 230;
            fourWay[idx + 1] = 210;
          } else if (x < 20) {
            fourWay[idx + 1] = 200;
          } else {
            fourWay[idx + 2] = 220;
          }
        }
      }
      expect(
        classifyCardColor(rgbBytes: fourWay, imageWidth: 40, imageHeight: 40),
        CardColor.wild,
      );
    });

    test('ignores outer margin pixels outside the center 60% crop', () {
      // Blue outer border, green center 60%.
      final bytes = _solidRgb(100, 100, 0, 0, 230);
      for (var y = 20; y < 80; y++) {
        for (var x = 20; x < 80; x++) {
          final idx = (y * 100 + x) * 3;
          bytes[idx] = 0;
          bytes[idx + 1] = 200;
          bytes[idx + 2] = 0;
        }
      }
      expect(
        classifyCardColor(rgbBytes: bytes, imageWidth: 100, imageHeight: 100),
        CardColor.green,
      );
    });
  });

  group('CardAnnouncer', () {
    final redSeven = _makeCard(CardColor.red, '7');
    final blueSkip = _makeCard(CardColor.blue, 'skip');

    void show(
      CardAnnouncer announcer,
      List<RecognizedCard> cards,
      int frames,
    ) {
      for (var i = 0; i < frames; i++) {
        announcer.observe(cards);
      }
    }

    test('announces once settled for 5 frames and does not repeat', () {
      final spoken = <String>[];
      final announcer = CardAnnouncer(say: spoken.add);

      show(announcer, [redSeven], stableFrameCount - 1);
      expect(spoken, isEmpty);

      announcer.observe([redSeven]);
      expect(spoken, ['red seven']);

      show(announcer, [redSeven], stableFrameCount * 5);
      expect(spoken, ['red seven']);
    });

    test('ignores brief dropout but re-announces after full removal', () {
      final spoken = <String>[];
      final announcer = CardAnnouncer(say: spoken.add);

      show(announcer, [redSeven], stableFrameCount);
      show(announcer, const [], stableFrameCount - 1);
      show(announcer, [redSeven], stableFrameCount);
      expect(spoken, ['red seven']);

      show(announcer, const [], stableFrameCount);
      show(announcer, [redSeven], stableFrameCount);
      expect(spoken, ['red seven', 'red seven']);
    });

    test('announces replacement card and picks highest confidence card', () {
      final spoken = <String>[];
      final announcer = CardAnnouncer(say: spoken.add);

      show(announcer, [redSeven], stableFrameCount);
      show(announcer, [blueSkip], stableFrameCount);
      expect(spoken, ['red seven', 'blue skip']);

      final faint = _makeCard(CardColor.green, '2', confidence: 0.52);
      final strong = _makeCard(CardColor.yellow, 'reverse', confidence: 0.94);
      show(announcer, [faint, strong], stableFrameCount);
      expect(spoken.last, 'yellow reverse');
    });
  });

  group('YOLO [1, 23, 8400] decoding & NMS', () {
    test('suppresses overlapping same-class boxes and unpads letterbox', () {
      final config = ModelConfig.defaults();
      const numAnchors = 8400;
      final raw = Float32List((4 + config.ranks.length) * numAnchors);

      void setAnchor({
        required int anchor,
        required double cx,
        required double cy,
        required double w,
        required double h,
        required int classIdx,
        required double score,
      }) {
        raw[anchor] = cx;
        raw[numAnchors + anchor] = cy;
        raw[2 * numAnchors + anchor] = w;
        raw[3 * numAnchors + anchor] = h;
        raw[(4 + classIdx) * numAnchors + anchor] = score;
      }

      // Portrait 480x640 letterboxed into 640x640 has scale = 1.0, padLeft = 80, padTop = 0.
      final sevenIdx = config.ranks.indexOf('7');
      final skipIdx = config.ranks.indexOf('skip');

      // Primary '7' detection centered at upright (200, 300), size 100x160 -> letterbox cx=280, cy=300
      setAnchor(
        anchor: 10,
        cx: 280,
        cy: 300,
        w: 100,
        h: 160,
        classIdx: sevenIdx,
        score: 0.91,
      );
      // Overlapping duplicate '7' detection -> should be suppressed by NMS
      setAnchor(
        anchor: 11,
        cx: 282,
        cy: 302,
        w: 100,
        h: 160,
        classIdx: sevenIdx,
        score: 0.72,
      );
      // Below-threshold noise -> should be ignored
      setAnchor(
        anchor: 50,
        cx: 200,
        cy: 150,
        w: 80,
        h: 120,
        classIdx: skipIdx,
        score: 0.30,
      );
      // Separate 'skip' card elsewhere -> should be kept
      setAnchor(
        anchor: 200,
        cx: 450,
        cy: 500,
        w: 80,
        h: 120,
        classIdx: skipIdx,
        score: 0.84,
      );

      final detections = decodeYoloOutput(
        rawOutput: raw,
        ranks: config.ranks,
        numAnchors: numAnchors,
        minConfidence: 0.5,
        iouThreshold: 0.45,
        letterboxScale: 1.0,
        padLeft: 80,
        padTop: 0,
        imageWidth: 480,
        imageHeight: 640,
      );

      expect(detections.length, 2);
      expect(detections[0].rank, '7');
      expect(detections[0].confidence, closeTo(0.91, 1e-5));
      expect(
        detections[0].box,
        const Box(x1: 150, y1: 220, x2: 250, y2: 380),
      );
      expect(detections[1].rank, 'skip');
      expect(
        detections[1].box,
        const Box(x1: 330, y1: 440, x2: 410, y2: 560),
      );
    });
  });

  group('Recognition & Frame preparation', () {
    test('maps back and wild directly and reads suit colors per box', () async {
      final config = ModelConfig.defaults();
      const width = 400;
      const height = 200;
      final rgb = Uint8List(width * height * 3);
      for (var y = 0; y < height; y++) {
        for (var x = 0; x < width; x++) {
          final idx = (y * width + x) * 3;
          if (x < 200) {
            rgb[idx] = 220; // Red left half
          } else {
            rgb[idx + 2] = 220; // Blue right half
          }
        }
      }

      final frame = PreparedFrame(
        rgbBytes: rgb,
        uprightWidth: width,
        uprightHeight: height,
        inputTensor: Float32List(3 * 16 * 16),
        inputSize: 16,
        letterboxScale: 1.0,
        padLeft: 0,
        padTop: 0,
      );

      final detector = _FakeDetector(const [
        Detection(
          rank: '7',
          confidence: 0.9,
          box: Box(x1: 0, y1: 0, x2: 200, y2: 200),
        ),
        Detection(
          rank: 'skip',
          confidence: 0.85,
          box: Box(x1: 200, y1: 0, x2: 400, y2: 200),
        ),
        Detection(
          rank: 'back',
          confidence: 0.88,
          box: Box(x1: 0, y1: 0, x2: 200, y2: 200),
        ),
        Detection(
          rank: 'joker',
          confidence: 0.86,
          box: Box(x1: 0, y1: 0, x2: 200, y2: 200),
        ),
      ]);

      final cards = await recognizeCards(frame, detector, config);
      expect(cards.map((c) => c.label).toList(), [
        'red 7',
        'blue skip',
        'back',
        'wild joker',
      ]);
    });

    test('rotates 90-degree sensor frame and pads letterbox with 114/255', () {
      // Raw 4x2 BGRA frame rotated 90 degrees CW -> upright 2x4.
      final bgra = Uint8List(4 * 2 * 4);
      for (var i = 0; i < bgra.length; i += 4) {
        bgra[i] = 0; // B
        bgra[i + 1] = 0; // G
        bgra[i + 2] = 255; // R
        bgra[i + 3] = 255; // A
      }
      final raw = RawCameraFrame(
        width: 4,
        height: 2,
        format: RawPixelFormat.bgra8888,
        planes: [RawPlaneData(bytes: bgra, bytesPerRow: 16, bytesPerPixel: 4)],
      );

      final prepared = prepareFrameSync(
        raw,
        sensorOrientation: 90,
        inputSize: 8,
      );
      expect(prepared.uprightWidth, 2);
      expect(prepared.uprightHeight, 4);
      expect(prepared.letterboxScale, 2.0);
      expect(prepared.padLeft, 2);
      expect(prepared.padTop, 0);
      // Left letterbox padding column (x=0, y=0) has gray 114/255.
      expect(prepared.inputTensor[0], closeTo(114.0 / 255.0, 1e-5));
      // Center unpadded pixel (x=3, y=1) has red channel = 1.0, green = 0.0.
      expect(prepared.inputTensor[1 * 8 + 3], closeTo(1.0, 1e-5));
      expect(prepared.inputTensor[64 + 1 * 8 + 3], closeTo(0.0, 1e-5));
    });
  });
}
