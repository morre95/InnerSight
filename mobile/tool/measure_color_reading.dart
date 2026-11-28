// Measures how well the app reads the color of a card, on the images of a dataset.
//
// The file name of an image tells the true color of its card, and its label file the box of
// the card, so no detector is needed. Run it from mobile/ before and after changing the values
// in lib/src/color_classifier.dart, to see whether the change helps:
//
//   dart run tool/measure_color_reading.dart [dataset directory]
//
// The images collected in games and in the app are counted apart from the recorded ones.

import 'dart:io';

import 'package:image/image.dart' as img;
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/color_classifier.dart';

const String defaultDatasetDirectory = '../datasets/phone-cards';
const List<String> splits = ['train', 'valid'];
const List<CardColor> suitColors = [
  CardColor.red,
  CardColor.yellow,
  CardColor.green,
  CardColor.blue,
];
const String recorded = 'Recorded';
const String collected = 'Collected in games and in the app';

/// For every true color, how often each color was read.
typedef Readings = Map<CardColor, Map<CardColor, int>>;

void main(List<String> arguments) {
  final dataset = Directory(
    arguments.isEmpty ? defaultDatasetDirectory : arguments.first,
  );
  if (!dataset.existsSync()) {
    stderr.writeln('There is no dataset in ${dataset.path}');
    exitCode = 1;
    return;
  }
  final readings = <String, Readings>{recorded: {}, collected: {}};
  for (final split in splits) {
    final images = Directory('${dataset.path}/$split/images').listSync()
      ..sort((a, b) => a.path.compareTo(b.path));
    for (final file in images.whereType<File>()) {
      _readImage(file, readings);
    }
  }
  readings.forEach(_printReadings);
}

void _readImage(File imageFile, Map<String, Readings> readings) {
  final name = imageFile.uri.pathSegments.last;
  if (!name.endsWith('.jpg')) {
    return;
  }
  // An image is named <color>_<rank>_<the rest>.
  final trueColor = suitColors
      .where((color) => name.startsWith('${color.name}_'))
      .firstOrNull;
  if (trueColor == null) {
    return;
  }
  final image = img.decodeJpg(imageFile.readAsBytesSync());
  if (image == null) {
    stderr.writeln('Could not read ${imageFile.path}');
    return;
  }
  final reading = classifyCardColor(
    rgbBytes: image.getBytes(order: img.ChannelOrder.rgb),
    imageWidth: image.width,
    imageHeight: image.height,
    box: _labeledBox(imageFile, image.width, image.height),
  );
  final isCollected = name.contains('_game_') || name.contains('_inbox_');
  final counts = readings[isCollected ? collected : recorded]!.putIfAbsent(
    trueColor,
    () => {},
  );
  counts[reading] = (counts[reading] ?? 0) + 1;
}

/// The box of the card in the label file of the image, in pixels.
Box _labeledBox(File imageFile, int imageWidth, int imageHeight) {
  final labelFile = File(
    imageFile.path
        .replaceFirst('/images/', '/labels/')
        .replaceFirst(RegExp(r'\.jpg$'), '.txt'),
  );
  // A label line is: class, then the center, width and height of the box as
  // shares of the image.
  final values = labelFile
      .readAsLinesSync()
      .first
      .split(' ')
      .skip(1)
      .map(double.parse)
      .toList();
  final [centerX, centerY, width, height] = values;
  return Box(
    x1: ((centerX - width / 2) * imageWidth).round(),
    y1: ((centerY - height / 2) * imageHeight).round(),
    x2: ((centerX + width / 2) * imageWidth).round(),
    y2: ((centerY + height / 2) * imageHeight).round(),
  );
}

void _printReadings(String group, Readings readings) {
  var imageCount = 0;
  var rightCount = 0;
  readings.forEach((color, counts) {
    imageCount += counts.values.fold(0, (sum, count) => sum + count);
    rightCount += counts[color] ?? 0;
  });
  stdout.writeln('$group: $rightCount of $imageCount colors read right');
  for (final color in suitColors) {
    final counts = readings[color];
    if (counts == null) {
      continue;
    }
    final total = counts.values.fold(0, (sum, count) => sum + count);
    final otherReadings = counts.entries
        .where((entry) => entry.key != color)
        .map((entry) => '${entry.key.name} ${entry.value}')
        .join(', ');
    final right = '${counts[color] ?? 0}'.padLeft(4);
    stdout.writeln(
      '  ${color.name.padRight(7)}$right of ${'$total'.padRight(4)} $otherReadings',
    );
  }
}
