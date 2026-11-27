import 'cards.dart';
import 'color_classifier.dart';
import 'frame_prep.dart';

/// A card whose box is as tall or as wide as this share of the frame does not
/// fit in the view.
const double fullViewFraction = 0.98;

/// Interface for a UNO card rank detector.
abstract interface class CardDetector {
  /// Finds the cards in [frame]. Detections below [minConfidence] are left
  /// out.
  Future<List<Detection>> detect(
    PreparedFrame frame, {
    required double minConfidence,
  });
}

/// Detects every card in [frame] and classifies its color.
///
/// Mirrors `recognize_cards` in `src/innersight/recognition.py`.
Future<List<RecognizedCard>> recognizeCards(
  PreparedFrame frame,
  CardDetector detector,
  ModelConfig config, {
  required double minConfidence,
}) async {
  final detections = await detector.detect(frame, minConfidence: minConfidence);
  return [
    for (final detection in detections)
      RecognizedCard(
        detection: detection,
        color: readCardColor(frame, detection, config),
        isTooClose: _fillsTheView(detection.box, frame),
      ),
  ];
}

bool _fillsTheView(Box box, PreparedFrame frame) {
  return box.height >= fullViewFraction * frame.uprightHeight ||
      box.width >= fullViewFraction * frame.uprightWidth;
}

/// Determines the [CardColor] for a single [detection]. Only a number or
/// action card has a color to read from the picture.
CardColor readCardColor(
  PreparedFrame frame,
  Detection detection,
  ModelConfig config,
) {
  return config.fixedColor(detection.rank) ??
      classifyCardColor(
        rgbBytes: frame.rgbBytes,
        imageWidth: frame.uprightWidth,
        imageHeight: frame.uprightHeight,
        box: detection.box,
      );
}
