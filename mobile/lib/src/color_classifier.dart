import 'dart:math' as math;
import 'dart:typed_data';

import 'cards.dart';

const int minSaturation = 70;
const int minValue = 50;
const double centerFraction = 0.6;
const double minColoredFraction = 0.05;
const double minDominantShare = 0.6;

/// The white of the card is taken from the brightest pixels: in each color
/// channel, the level that this share of the box stays below.
const double whitePercentile = 0.9;

/// Classifies the suit color of a UNO card from a packed RGB image and optional [box].
///
/// Hue is OpenCV-scaled and runs in `0..179`. The tint of the light is removed first, as in
/// `classify_card_color` in `src/innersight/color.py`. The hue ranges and thresholds are tuned
/// for the phone camera and differ on purpose from the ones there, which are tuned for a
/// webcam (docs/adr/0001).
CardColor classifyCardColor({
  required Uint8List rgbBytes,
  required int imageWidth,
  required int imageHeight,
  Box? box,
}) {
  if (imageWidth <= 0 || imageHeight <= 0) {
    return CardColor.unknown;
  }

  final x1 = (box?.x1 ?? 0).clamp(0, imageWidth);
  final y1 = (box?.y1 ?? 0).clamp(0, imageHeight);
  final x2 = (box?.x2 ?? imageWidth).clamp(0, imageWidth);
  final y2 = (box?.y2 ?? imageHeight).clamp(0, imageHeight);

  final cropWidth = x2 - x1;
  final cropHeight = y2 - y1;
  if (cropWidth <= 0 || cropHeight <= 0) {
    return CardColor.unknown;
  }

  final marginY = (cropHeight * (1.0 - centerFraction) / 2.0).round();
  final marginX = (cropWidth * (1.0 - centerFraction) / 2.0).round();

  var centerX1 = x1 + marginX;
  var centerX2 = x2 - marginX;
  var centerY1 = y1 + marginY;
  var centerY2 = y2 - marginY;
  if (centerX2 <= centerX1) {
    centerX1 = x1;
    centerX2 = x2;
  }
  if (centerY2 <= centerY1) {
    centerY1 = y1;
    centerY2 = y2;
  }

  final totalPixels = (centerX2 - centerX1) * (centerY2 - centerY1);
  if (totalPixels <= 0) {
    return CardColor.unknown;
  }

  var coloredPixels = 0;
  var redCount = 0;
  var yellowCount = 0;
  var greenCount = 0;
  var blueCount = 0;

  final (redGain, greenGain, blueGain) = _whiteBalanceGains(
    rgbBytes,
    imageWidth,
    x1: x1,
    y1: y1,
    x2: x2,
    y2: y2,
  );

  final rowStride = imageWidth * 3;
  for (var y = centerY1; y < centerY2; y++) {
    final rowOffset = y * rowStride;
    for (var x = centerX1; x < centerX2; x++) {
      final offset = rowOffset + x * 3;
      final (hue, sat, val) = rgbToOpenCvHsv(
        math.min(255, (rgbBytes[offset] * redGain).round()),
        math.min(255, (rgbBytes[offset + 1] * greenGain).round()),
        math.min(255, (rgbBytes[offset + 2] * blueGain).round()),
      );
      if (sat < minSaturation || val < minValue) {
        continue;
      }
      coloredPixels++;
      if ((hue >= 0 && hue < 12) || (hue >= 160 && hue < 180)) {
        redCount++;
      } else if (hue >= 12 && hue < 40) {
        yellowCount++;
      } else if (hue >= 40 && hue < 90) {
        greenCount++;
      } else if (hue >= 90 && hue < 140) {
        blueCount++;
      }
    }
  }

  if (coloredPixels < minColoredFraction * totalPixels) {
    return CardColor.unknown;
  }

  final counts = <CardColor, int>{
    CardColor.red: redCount,
    CardColor.yellow: yellowCount,
    CardColor.green: greenCount,
    CardColor.blue: blueCount,
  };

  var dominantColor = CardColor.red;
  var dominantCount = -1;
  for (final entry in counts.entries) {
    if (entry.value > dominantCount) {
      dominantCount = entry.value;
      dominantColor = entry.key;
    }
  }

  if (dominantCount < minDominantShare * coloredPixels) {
    return CardColor.unknown;
  }
  return dominantColor;
}

/// How much to scale red, green and blue to remove the tint of the light, so
/// that the white of the card becomes white.
///
/// A card has a white border and a white digit. Scaling every color channel
/// so that its brightest pixels reach the same level takes away the tint that
/// the light gives them, and with it the tint it gives the color of the card.
/// The whole box is used, as the white border lies outside its middle.
(double, double, double) _whiteBalanceGains(
  Uint8List rgbBytes,
  int imageWidth, {
  required int x1,
  required int y1,
  required int x2,
  required int y2,
}) {
  final levelCounts = [
    for (var channel = 0; channel < 3; channel++) List<int>.filled(256, 0),
  ];
  for (var y = y1; y < y2; y++) {
    var offset = (y * imageWidth + x1) * 3;
    for (var x = x1; x < x2; x++) {
      levelCounts[0][rgbBytes[offset]]++;
      levelCounts[1][rgbBytes[offset + 1]]++;
      levelCounts[2][rgbBytes[offset + 2]]++;
      offset += 3;
    }
  }

  final pixelsBelowWhite = ((x2 - x1) * (y2 - y1) * whitePercentile).floor();
  final white = [
    for (final counts in levelCounts) _levelAbove(counts, pixelsBelowWhite),
  ];
  final brightest = white.reduce(math.max);
  return (
    brightest / math.max(white[0], 1),
    brightest / math.max(white[1], 1),
    brightest / math.max(white[2], 1),
  );
}

/// The lowest level that more than [pixelCount] pixels are at or below.
int _levelAbove(List<int> levelCounts, int pixelCount) {
  var seen = 0;
  for (var level = 0; level < levelCounts.length; level++) {
    seen += levelCounts[level];
    if (seen > pixelCount) {
      return level;
    }
  }
  return levelCounts.length - 1;
}

/// Converts 8-bit RGB (`0..255`) into OpenCV 8-bit HSV (`H: 0..179, S: 0..255, V: 0..255`).
(int, int, int) rgbToOpenCvHsv(int r, int g, int b) {
  final vmax = math.max(r, math.max(g, b));
  final vmin = math.min(r, math.min(g, b));
  final diff = vmax - vmin;

  final value = vmax;
  final saturation = vmax == 0 ? 0 : ((diff * 255 + (vmax >> 1)) ~/ vmax);
  if (diff == 0) {
    return (0, saturation, value);
  }

  double hue;
  if (vmax == r) {
    hue = 30.0 * (g - b) / diff;
  } else if (vmax == g) {
    hue = 60.0 + 30.0 * (b - r) / diff;
  } else {
    hue = 120.0 + 30.0 * (r - g) / diff;
  }
  if (hue < 0.0) {
    hue += 180.0;
  }
  final quantizedHue = hue.round() % 180;
  return (quantizedHue, saturation, value);
}
