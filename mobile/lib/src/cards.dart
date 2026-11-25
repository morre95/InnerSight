import 'dart:convert';

/// Colors of UNO cards recognized by InnerSight.
enum CardColor {
  red('red'),
  yellow('yellow'),
  green('green'),
  blue('blue'),
  wild('wild'),
  back('back'),

  /// The color of a number or action card could not be read from the picture.
  unknown('unknown');

  const CardColor(this.value);
  final String value;

  @override
  String toString() => value;
}

const List<CardColor> suitColors = [
  CardColor.red,
  CardColor.yellow,
  CardColor.green,
  CardColor.blue,
];

/// Model class metadata exported alongside `own-cards.onnx`.
class ModelConfig {
  ModelConfig({
    required this.inputSize,
    required this.ranks,
    required Iterable<String> wildRanks,
    required this.backRank,
    required Map<String, String> spokenRanks,
  }) : wildRanks = Set<String>.unmodifiable(wildRanks),
       spokenRanks = Map<String, String>.unmodifiable(spokenRanks);

  factory ModelConfig.fromJsonString(String rawJson) {
    final decoded = jsonDecode(rawJson) as Map<String, dynamic>;
    return ModelConfig.fromJson(decoded);
  }

  factory ModelConfig.fromJson(Map<String, dynamic> json) {
    return ModelConfig(
      inputSize: (json['input_size'] as num?)?.toInt() ?? 640,
      ranks: List<String>.unmodifiable(
        (json['ranks'] as List<dynamic>).map((item) => item as String),
      ),
      wildRanks: (json['wild_ranks'] as List<dynamic>).map(
        (item) => item as String,
      ),
      backRank: json['back_rank'] as String? ?? 'back',
      spokenRanks: (json['spoken_ranks'] as Map<String, dynamic>).map(
        (key, value) => MapEntry(key, value as String),
      ),
    );
  }

  factory ModelConfig.defaults() {
    return ModelConfig(
      inputSize: 640,
      ranks: const [
        '0',
        '1',
        '2',
        '3',
        '4',
        '5',
        '6',
        '7',
        '8',
        '9',
        'skip',
        'reverse',
        '+2',
        'wild',
        '+4',
        'back',
        'shuffle',
        'joker',
        'customizable',
      ],
      wildRanks: const ['wild', '+4', 'shuffle', 'joker', 'customizable'],
      backRank: 'back',
      spokenRanks: defaultSpokenRanks,
    );
  }

  final int inputSize;
  final List<String> ranks;
  final Set<String> wildRanks;
  final String backRank;
  final Map<String, String> spokenRanks;
}

const Map<String, String> defaultSpokenRanks = {
  '0': 'zero',
  '1': 'one',
  '2': 'two',
  '3': 'three',
  '4': 'four',
  '5': 'five',
  '6': 'six',
  '7': 'seven',
  '8': 'eight',
  '9': 'nine',
  'skip': 'skip',
  'reverse': 'reverse',
  '+2': 'draw two',
  'wild': 'wild',
  '+4': 'draw four',
  'back': 'card back',
  'shuffle': 'shuffle',
  'joker': 'joker',
  'customizable': 'customizable',
};

/// What one side of a card shows: one of the UNO designs, or the back.
class CardFace {
  const CardFace({required this.color, required this.rank});

  final CardColor color;
  final String rank;

  /// Human-readable name, such as "red 7", "wild", "wild +4", or "back".
  String get label => describe(rank);

  /// Name the card with the given wording for its rank, such as "seven" for "7".
  String describe(String rankWording) {
    if (rank == color.value) {
      return rankWording;
    }
    return '${color.value} $rankWording';
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CardFace && color == other.color && rank == other.rank;

  @override
  int get hashCode => Object.hash(color, rank);

  @override
  String toString() => 'CardFace($label)';
}

/// Pixel rectangle in an upright frame: (x1, y1) top-left, (x2, y2) bottom-right.
class Box {
  const Box({
    required this.x1,
    required this.y1,
    required this.x2,
    required this.y2,
  });

  final int x1;
  final int y1;
  final int x2;
  final int y2;

  int get width => x2 - x1;
  int get height => y2 - y1;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Box &&
          x1 == other.x1 &&
          y1 == other.y1 &&
          x2 == other.x2 &&
          y2 == other.y2;

  @override
  int get hashCode => Object.hash(x1, y1, x2, y2);

  @override
  String toString() => 'Box($x1, $y1, $x2, $y2)';
}

/// A card found in a frame, before its color is classified.
class Detection {
  const Detection({
    required this.rank,
    required this.confidence,
    required this.box,
  });

  final String rank;
  final double confidence;
  final Box box;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Detection &&
          rank == other.rank &&
          confidence == other.confidence &&
          box == other.box;

  @override
  int get hashCode => Object.hash(rank, confidence, box);
}

/// A detected card together with its classified color.
///
/// A card [isTooClose] when it does not fit in the view of the camera. It can
/// often still be read, but any closer and the detector loses it.
class RecognizedCard {
  const RecognizedCard({
    required this.detection,
    required this.color,
    this.isTooClose = false,
  });

  final Detection detection;
  final CardColor color;
  final bool isTooClose;

  CardFace get face => CardFace(color: color, rank: detection.rank);

  String get label => face.label;
}
