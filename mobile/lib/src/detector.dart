import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/services.dart';
import 'package:flutter_onnxruntime/flutter_onnxruntime.dart';

import 'cards.dart';
import 'frame_prep.dart';
import 'recognition.dart';

/// Runs YOLO ONNX card rank detection and NMS on [PreparedFrame] inputs.
class OnnxCardDetector implements CardDetector {
  OnnxCardDetector._({
    required OrtSession session,
    required this.config,
    required this.iouThreshold,
  }) : _session = session,
       _inputName = session.inputNames.first,
       _outputName = session.outputNames.first;

  static Future<OnnxCardDetector> fromAssets({
    String modelAsset = 'assets/models/own-cards.onnx',
    String configAsset = 'assets/models/model_config.json',
    double iouThreshold = 0.45,
  }) async {
    final configJson = await rootBundle.loadString(configAsset);
    final config = ModelConfig.fromJsonString(configJson);
    final modelPath = await _materializeModelAsset(modelAsset);
    final ort = OnnxRuntime();

    OrtSession session;
    try {
      session = await ort.createSession(
        modelPath,
        options: OrtSessionOptions(
          intraOpNumThreads: 4,
          providers: [OrtProvider.XNNPACK, OrtProvider.CPU],
        ),
      );
    } catch (_) {
      session = await ort.createSession(
        modelPath,
        options: OrtSessionOptions(intraOpNumThreads: 4),
      );
    }

    return OnnxCardDetector._(
      session: session,
      config: config,
      iouThreshold: iouThreshold,
    );
  }

  /// Writes [modelAsset] to a content-hashed file in [Directory.systemTemp] so
  /// re-exporting new weights with the same asset name never loads a stale cache.
  static Future<String> _materializeModelAsset(String modelAsset) async {
    final byteData = await rootBundle.load(modelAsset);
    final bytes = byteData.buffer.asUint8List(
      byteData.offsetInBytes,
      byteData.lengthInBytes,
    );

    // 32-bit FNV-1a fingerprint sampled across the buffer + exact byte length.
    var hash = 0x811c9dc5;
    final step = math.max(1, bytes.length ~/ 4096);
    for (var i = 0; i < bytes.length; i += step) {
      hash ^= bytes[i];
      hash = (hash * 0x01000193) & 0xffffffff;
    }
    final hexHash = hash.toRadixString(16).padLeft(8, '0');
    final file = File(
      '${Directory.systemTemp.path}${Platform.pathSeparator}'
      'own-cards-${bytes.length}-$hexHash.onnx',
    );
    if (!await file.exists()) {
      final tmp = File('${file.path}.tmp');
      await tmp.writeAsBytes(bytes, flush: true);
      await tmp.rename(file.path);
    }
    return file.path;
  }

  final OrtSession _session;
  final String _inputName;
  final String _outputName;
  final ModelConfig config;
  final double iouThreshold;

  @override
  Future<List<Detection>> detect(
    PreparedFrame frame, {
    required double minConfidence,
  }) async {
    final inputValue = await OrtValue.fromList(frame.inputTensor, [
      1,
      3,
      frame.inputSize,
      frame.inputSize,
    ]);
    Map<String, OrtValue>? outputs;
    try {
      outputs = await _session.run({_inputName: inputValue});
      final outputValue = outputs[_outputName] ?? outputs.values.first;
      final shape = outputValue.shape;
      final numAnchors = shape.length >= 3 ? shape[2] : 8400;
      final flat = (await outputValue.asFlattenedList()).cast<num>();
      return decodeYoloOutput(
        rawOutput: flat,
        ranks: config.ranks,
        numAnchors: numAnchors,
        minConfidence: minConfidence,
        iouThreshold: iouThreshold,
        letterboxScale: frame.letterboxScale,
        padLeft: frame.padLeft,
        padTop: frame.padTop,
        imageWidth: frame.uprightWidth,
        imageHeight: frame.uprightHeight,
      );
    } finally {
      await inputValue.dispose();
      if (outputs != null) {
        for (final tensor in outputs.values) {
          await tensor.dispose();
        }
      }
    }
  }

  Future<void> dispose() async {
    await _session.close();
  }
}

class _CandidateBox {
  const _CandidateBox({
    required this.classIndex,
    required this.confidence,
    required this.x1,
    required this.y1,
    required this.x2,
    required this.y2,
  });

  final int classIndex;
  final double confidence;
  final double x1;
  final double y1;
  final double x2;
  final double y2;
}

/// Decodes Ultralytics `[1, 4 + numClasses, numAnchors]` output, runs class-aware
/// NMS, and rescales boxes from letterbox pixels back to upright image pixels.
List<Detection> decodeYoloOutput({
  required List<num> rawOutput,
  required List<String> ranks,
  int numAnchors = 8400,
  double minConfidence = 0.5,
  double iouThreshold = 0.45,
  required double letterboxScale,
  required int padLeft,
  required int padTop,
  required int imageWidth,
  required int imageHeight,
}) {
  if (numAnchors <= 0 || letterboxScale <= 0) {
    return const [];
  }
  final tensorChannels = rawOutput.length ~/ numAnchors;
  final tensorClasses = tensorChannels - 4;
  final usableClasses = math.min(ranks.length, tensorClasses);
  if (usableClasses <= 0 || rawOutput.length < tensorChannels * numAnchors) {
    return const [];
  }

  final candidates = <_CandidateBox>[];
  for (var anchor = 0; anchor < numAnchors; anchor++) {
    var bestClass = -1;
    var bestScore = minConfidence;
    for (var cls = 0; cls < usableClasses; cls++) {
      final score = rawOutput[(4 + cls) * numAnchors + anchor].toDouble();
      if (score > bestScore || (bestClass == -1 && score >= minConfidence)) {
        bestScore = score;
        bestClass = cls;
      }
    }
    if (bestClass < 0) continue;

    final cx = rawOutput[anchor].toDouble();
    final cy = rawOutput[numAnchors + anchor].toDouble();
    final w = rawOutput[2 * numAnchors + anchor].toDouble();
    final h = rawOutput[3 * numAnchors + anchor].toDouble();
    if (w <= 0 || h <= 0) continue;

    final halfW = w * 0.5;
    final halfH = h * 0.5;
    candidates.add(
      _CandidateBox(
        classIndex: bestClass,
        confidence: bestScore,
        x1: cx - halfW,
        y1: cy - halfH,
        x2: cx + halfW,
        y2: cy + halfH,
      ),
    );
  }

  if (candidates.isEmpty) {
    return const [];
  }

  candidates.sort((a, b) => b.confidence.compareTo(a.confidence));

  final kept = <_CandidateBox>[];
  for (final candidate in candidates) {
    var suppressed = false;
    for (final existing in kept) {
      if (existing.classIndex == candidate.classIndex &&
          _iou(existing, candidate) > iouThreshold) {
        suppressed = true;
        break;
      }
    }
    if (!suppressed) {
      kept.add(candidate);
    }
  }

  final detections = <Detection>[];
  for (final box in kept) {
    final unpaddedX1 = ((box.x1 - padLeft) / letterboxScale).round().clamp(
      0,
      imageWidth,
    );
    final unpaddedY1 = ((box.y1 - padTop) / letterboxScale).round().clamp(
      0,
      imageHeight,
    );
    final unpaddedX2 = ((box.x2 - padLeft) / letterboxScale).round().clamp(
      0,
      imageWidth,
    );
    final unpaddedY2 = ((box.y2 - padTop) / letterboxScale).round().clamp(
      0,
      imageHeight,
    );

    if (unpaddedX2 <= unpaddedX1 || unpaddedY2 <= unpaddedY1) {
      continue;
    }

    detections.add(
      Detection(
        rank: ranks[box.classIndex],
        confidence: box.confidence,
        box: Box(
          x1: unpaddedX1,
          y1: unpaddedY1,
          x2: unpaddedX2,
          y2: unpaddedY2,
        ),
      ),
    );
  }
  return detections;
}

double _iou(_CandidateBox a, _CandidateBox b) {
  final interX1 = math.max(a.x1, b.x1);
  final interY1 = math.max(a.y1, b.y1);
  final interX2 = math.min(a.x2, b.x2);
  final interY2 = math.min(a.y2, b.y2);

  final interW = math.max(0.0, interX2 - interX1);
  final interH = math.max(0.0, interY2 - interY1);
  final interArea = interW * interH;
  if (interArea <= 0.0) return 0.0;

  final areaA = (a.x2 - a.x1) * (a.y2 - a.y1);
  final areaB = (b.x2 - b.x1) * (b.y2 - b.y1);
  final unionArea = areaA + areaB - interArea;
  return unionArea <= 0.0 ? 0.0 : interArea / unionArea;
}
