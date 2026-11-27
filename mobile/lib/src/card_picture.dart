import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'cards.dart';

/// A picture of one card, or of a whole frame, as packed RGBA pixels.
class CardPicture {
  const CardPicture({
    required this.rgbaBytes,
    required this.width,
    required this.height,
  });

  final Uint8List rgbaBytes;
  final int width;
  final int height;
}

/// The whole frame the card of a round was read in, and the card as it was
/// read there. This is what a training example is made of.
class RoundFrame {
  const RoundFrame({
    required this.rgbBytes,
    required this.width,
    required this.height,
    required this.card,
  });

  /// The upright frame as packed RGB pixels, not mirrored.
  final Uint8List rgbBytes;
  final int width;
  final int height;
  final RecognizedCard card;

  /// The whole frame as a picture.
  CardPicture get picture => cropCardPicture(
    rgbBytes,
    width,
    Box(x1: 0, y1: 0, x2: width, y2: height),
  );
}

/// Cuts the part inside [box] out of a frame of packed RGB pixels that is
/// [frameWidth] wide.
///
/// The frame is upright and not mirrored, so the card reads as it does in the
/// hand, also on the front camera.
CardPicture cropCardPicture(Uint8List rgbBytes, int frameWidth, Box box) {
  final rgbaBytes = Uint8List(box.width * box.height * 4);
  var target = 0;
  for (var y = box.y1; y < box.y2; y++) {
    var source = (y * frameWidth + box.x1) * 3;
    for (var x = box.x1; x < box.x2; x++) {
      rgbaBytes[target] = rgbBytes[source];
      rgbaBytes[target + 1] = rgbBytes[source + 1];
      rgbaBytes[target + 2] = rgbBytes[source + 2];
      rgbaBytes[target + 3] = 255;
      source += 3;
      target += 4;
    }
  }
  return CardPicture(
    rgbaBytes: rgbaBytes,
    width: box.width,
    height: box.height,
  );
}

/// Turns [picture] into an image that can be drawn. The caller disposes it.
Future<ui.Image> decodePicture(CardPicture picture) {
  final decoded = Completer<ui.Image>();
  ui.decodeImageFromPixels(
    picture.rgbaBytes,
    picture.width,
    picture.height,
    ui.PixelFormat.rgba8888,
    decoded.complete,
  );
  return decoded.future;
}

/// Packs [picture] as a PNG file, which loses nothing of it.
Future<Uint8List> encodePng(CardPicture picture) async {
  final image = await decodePicture(picture);
  try {
    final png = await image.toByteData(format: ui.ImageByteFormat.png);
    if (png == null) {
      throw StateError('The picture could not be packed as a PNG');
    }
    return png.buffer.asUint8List();
  } finally {
    image.dispose();
  }
}
