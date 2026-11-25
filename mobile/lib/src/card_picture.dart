import 'dart:typed_data';

import 'cards.dart';
import 'frame_prep.dart';

/// A picture of one card, cut from a camera frame, as packed RGBA pixels.
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

/// Cuts the part of [frame] inside [box] out as a picture.
///
/// The frame is upright and not mirrored, so the card reads as it does in the
/// hand, also on the front camera.
CardPicture cropCardPicture(PreparedFrame frame, Box box) {
  final rgbaBytes = Uint8List(box.width * box.height * 4);
  var target = 0;
  for (var y = box.y1; y < box.y2; y++) {
    var source = (y * frame.uprightWidth + box.x1) * 3;
    for (var x = box.x1; x < box.x2; x++) {
      rgbaBytes[target] = frame.rgbBytes[source];
      rgbaBytes[target + 1] = frame.rgbBytes[source + 1];
      rgbaBytes[target + 2] = frame.rgbBytes[source + 2];
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
