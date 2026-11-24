import 'cards.dart';
import 'color_classifier.dart';
import 'frame_prep.dart';

/// Interface for a UNO card rank detector.
abstract interface class CardDetector {
  Future<List<Detection>> detect(PreparedFrame frame);
}

/// Detects every card in [frame] and classifies its color.
///
/// Mirrors `recognize_cards` in `src/innersight/recognition.py`.
Future<List<RecognizedCard>> recognizeCards(
  PreparedFrame frame,
  CardDetector detector,
  ModelConfig config,
) async {
  final detections = await detector.detect(frame);
  return [
    for (final detection in detections)
      RecognizedCard(
        detection: detection,
        color: readCardColor(frame, detection, config),
      ),
  ];
}

/// Determines the [CardColor] for a single [detection].
CardColor readCardColor(
  PreparedFrame frame,
  Detection detection,
  ModelConfig config,
) {
  if (detection.rank == config.backRank) {
    return CardColor.back;
  }
  if (config.wildRanks.contains(detection.rank)) {
    return CardColor.wild;
  }
  return classifyCardColor(
    rgbBytes: frame.rgbBytes,
    imageWidth: frame.uprightWidth,
    imageHeight: frame.uprightHeight,
    box: detection.box,
  );
}
