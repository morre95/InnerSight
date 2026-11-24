import 'dart:isolate';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:camera/camera.dart';

/// Sendable snapshot of one plane from a [CameraImage].
class RawPlaneData {
  const RawPlaneData({
    required this.bytes,
    required this.bytesPerRow,
    required this.bytesPerPixel,
  });

  final Uint8List bytes;
  final int bytesPerRow;
  final int bytesPerPixel;
}

/// Pixel buffer format of a [RawCameraFrame].
enum RawPixelFormat { yuv420, nv21, bgra8888 }

/// Pure-Dart camera buffer transferable to a background isolate.
class RawCameraFrame {
  const RawCameraFrame({
    required this.width,
    required this.height,
    required this.format,
    required this.planes,
  });

  factory RawCameraFrame.fromCameraImage(CameraImage image) {
    final format = switch (image.format.group) {
      ImageFormatGroup.nv21 => RawPixelFormat.nv21,
      ImageFormatGroup.bgra8888 => RawPixelFormat.bgra8888,
      _ => RawPixelFormat.yuv420,
    };
    return RawCameraFrame(
      width: image.width,
      height: image.height,
      format: format,
      planes: [
        for (final plane in image.planes)
          RawPlaneData(
            bytes: Uint8List.fromList(plane.bytes),
            bytesPerRow: plane.bytesPerRow,
            bytesPerPixel: plane.bytesPerPixel ?? 1,
          ),
      ],
    );
  }

  final int width;
  final int height;
  final RawPixelFormat format;
  final List<RawPlaneData> planes;
}

/// Upright RGB buffer and letterboxed NCHW tensor ready for ONNX and HSV crops.
class PreparedFrame {
  const PreparedFrame({
    required this.rgbBytes,
    required this.uprightWidth,
    required this.uprightHeight,
    required this.inputTensor,
    required this.inputSize,
    required this.letterboxScale,
    required this.padLeft,
    required this.padTop,
  });

  final Uint8List rgbBytes;
  final int uprightWidth;
  final int uprightHeight;
  final Float32List inputTensor;
  final int inputSize;
  final double letterboxScale;
  final int padLeft;
  final int padTop;
}

/// Converts and letterboxes [image] on a background isolate.
Future<PreparedFrame> prepareCameraFrame(
  CameraImage image, {
  required int sensorOrientation,
  int inputSize = 640,
}) {
  final rawFrame = RawCameraFrame.fromCameraImage(image);
  return Isolate.run(
    () => prepareFrameSync(
      rawFrame,
      sensorOrientation: sensorOrientation,
      inputSize: inputSize,
    ),
  );
}

/// Synchronous worker that rotates [frame] to upright RGB and builds `[1, 3, S, S]`.
PreparedFrame prepareFrameSync(
  RawCameraFrame frame, {
  required int sensorOrientation,
  int inputSize = 640,
}) {
  final normalizedRotation = ((sensorOrientation % 360) + 360) % 360;
  final swapDimensions = normalizedRotation == 90 || normalizedRotation == 270;
  final uprightWidth = swapDimensions ? frame.height : frame.width;
  final uprightHeight = swapDimensions ? frame.width : frame.height;

  final rgbBytes = _extractUprightRgb(
    frame,
    rotationDegrees: normalizedRotation,
    uprightWidth: uprightWidth,
    uprightHeight: uprightHeight,
  );

  final scale = math.min(
    inputSize / uprightWidth,
    inputSize / uprightHeight,
  );
  final unpaddedWidth = (uprightWidth * scale).round();
  final unpaddedHeight = (uprightHeight * scale).round();
  final dw = (inputSize - unpaddedWidth) / 2.0;
  final dh = (inputSize - unpaddedHeight) / 2.0;
  final padLeft = (dw - 0.1).round();
  final padTop = (dh - 0.1).round();

  final inputTensor = _buildLetterboxTensor(
    rgbBytes: rgbBytes,
    srcWidth: uprightWidth,
    srcHeight: uprightHeight,
    inputSize: inputSize,
    dstWidth: unpaddedWidth,
    dstHeight: unpaddedHeight,
    padLeft: padLeft,
    padTop: padTop,
  );

  return PreparedFrame(
    rgbBytes: rgbBytes,
    uprightWidth: uprightWidth,
    uprightHeight: uprightHeight,
    inputTensor: inputTensor,
    inputSize: inputSize,
    letterboxScale: scale,
    padLeft: padLeft,
    padTop: padTop,
  );
}

Uint8List _extractUprightRgb(
  RawCameraFrame frame, {
  required int rotationDegrees,
  required int uprightWidth,
  required int uprightHeight,
}) {
  final rawWidth = frame.width;
  final rawHeight = frame.height;
  final rgb = Uint8List(uprightWidth * uprightHeight * 3);

  if (frame.format == RawPixelFormat.bgra8888 || frame.planes.length == 1 && frame.planes.first.bytesPerPixel == 4) {
    final plane = frame.planes.first;
    final bytes = plane.bytes;
    final rowStride = plane.bytesPerRow;
    var outIdx = 0;
    for (var dy = 0; dy < uprightHeight; dy++) {
      for (var dx = 0; dx < uprightWidth; dx++) {
        final (sx, sy) = _mapToRaw(dx, dy, rawWidth, rawHeight, rotationDegrees);
        final idx = sy * rowStride + sx * 4;
        rgb[outIdx++] = bytes[idx + 2];
        rgb[outIdx++] = bytes[idx + 1];
        rgb[outIdx++] = bytes[idx];
      }
    }
    return rgb;
  }

  if (frame.format == RawPixelFormat.nv21 || frame.planes.length < 3) {
    final yPlane = frame.planes[0];
    final yBytes = yPlane.bytes;
    final yRowStride = yPlane.bytesPerRow;
    final vuBytes = frame.planes.length > 1 ? frame.planes[1].bytes : yBytes;
    final vuOffset = frame.planes.length > 1 ? 0 : yRowStride * rawHeight;
    final vuRowStride = frame.planes.length > 1 ? frame.planes[1].bytesPerRow : rawWidth;

    var outIdx = 0;
    for (var dy = 0; dy < uprightHeight; dy++) {
      for (var dx = 0; dx < uprightWidth; dx++) {
        final (sx, sy) = _mapToRaw(dx, dy, rawWidth, rawHeight, rotationDegrees);
        final yVal = yBytes[sy * yRowStride + sx];
        final uvIdx = vuOffset + (sy >> 1) * vuRowStride + ((sx >> 1) << 1);
        final vVal = uvIdx < vuBytes.length ? vuBytes[uvIdx] : 128;
        final uVal = (uvIdx + 1) < vuBytes.length ? vuBytes[uvIdx + 1] : 128;
        _writeYuvAsRgb(rgb, outIdx, yVal, uVal, vVal);
        outIdx += 3;
      }
    }
    return rgb;
  }

  final yPlane = frame.planes[0];
  final uPlane = frame.planes[1];
  final vPlane = frame.planes[2];
  final yBytes = yPlane.bytes;
  final uBytes = uPlane.bytes;
  final vBytes = vPlane.bytes;
  final yRowStride = yPlane.bytesPerRow;
  final yPixelStride = yPlane.bytesPerPixel;
  final uRowStride = uPlane.bytesPerRow;
  final uPixelStride = uPlane.bytesPerPixel;
  final vRowStride = vPlane.bytesPerRow;
  final vPixelStride = vPlane.bytesPerPixel;

  var outIdx = 0;
  for (var dy = 0; dy < uprightHeight; dy++) {
    for (var dx = 0; dx < uprightWidth; dx++) {
      final (sx, sy) = _mapToRaw(dx, dy, rawWidth, rawHeight, rotationDegrees);
      final yIdx = sy * yRowStride + sx * yPixelStride;
      final uvX = sx >> 1;
      final uvY = sy >> 1;
      final uIdx = uvY * uRowStride + uvX * uPixelStride;
      final vIdx = uvY * vRowStride + uvX * vPixelStride;

      final yVal = yBytes[yIdx];
      final uVal = uIdx < uBytes.length ? uBytes[uIdx] : 128;
      final vVal = vIdx < vBytes.length ? vBytes[vIdx] : 128;
      _writeYuvAsRgb(rgb, outIdx, yVal, uVal, vVal);
      outIdx += 3;
    }
  }
  return rgb;
}

@pragma('vm:prefer-inline')
(int, int) _mapToRaw(int dx, int dy, int rawWidth, int rawHeight, int rotationDegrees) {
  return switch (rotationDegrees) {
    90 => (dy, rawHeight - 1 - dx),
    180 => (rawWidth - 1 - dx, rawHeight - 1 - dy),
    270 => (rawWidth - 1 - dy, dx),
    _ => (dx, dy),
  };
}

@pragma('vm:prefer-inline')
void _writeYuvAsRgb(Uint8List rgb, int offset, int y, int u, int v) {
  final uShift = u - 128;
  final vShift = v - 128;
  final r = y + ((1436 * vShift) >> 10);
  final g = y - ((352 * uShift + 731 * vShift) >> 10);
  final b = y + ((1815 * uShift) >> 10);
  rgb[offset] = r < 0 ? 0 : (r > 255 ? 255 : r);
  rgb[offset + 1] = g < 0 ? 0 : (g > 255 ? 255 : g);
  rgb[offset + 2] = b < 0 ? 0 : (b > 255 ? 255 : b);
}

Float32List _buildLetterboxTensor({
  required Uint8List rgbBytes,
  required int srcWidth,
  required int srcHeight,
  required int inputSize,
  required int dstWidth,
  required int dstHeight,
  required int padLeft,
  required int padTop,
}) {
  final planeSize = inputSize * inputSize;
  final tensor = Float32List(3 * planeSize);
  const padValue = 114.0 / 255.0;
  tensor.fillRange(0, tensor.length, padValue);

  if (dstWidth <= 0 || dstHeight <= 0) {
    return tensor;
  }

  // Precompute horizontal bilinear weights matching OpenCV INTER_LINEAR.
  final x0List = Int32List(dstWidth);
  final x1List = Int32List(dstWidth);
  final wxList = Float32List(dstWidth);
  final scaleX = srcWidth / dstWidth;
  for (var dx = 0; dx < dstWidth; dx++) {
    final fx = (dx + 0.5) * scaleX - 0.5;
    final clamped = fx < 0.0 ? 0.0 : (fx > srcWidth - 1 ? (srcWidth - 1).toDouble() : fx);
    final x0 = clamped.floor();
    final x1 = x0 + 1 < srcWidth ? x0 + 1 : x0;
    x0List[dx] = x0 * 3;
    x1List[dx] = x1 * 3;
    wxList[dx] = clamped - x0;
  }

  final scaleY = srcHeight / dstHeight;
  const inv255 = 1.0 / 255.0;
  final gPlaneOffset = planeSize;
  final bPlaneOffset = 2 * planeSize;
  final srcRowBytes = srcWidth * 3;

  for (var dy = 0; dy < dstHeight; dy++) {
    final targetY = padTop + dy;
    if (targetY < 0 || targetY >= inputSize) continue;

    final fy = (dy + 0.5) * scaleY - 0.5;
    final clampedY = fy < 0.0 ? 0.0 : (fy > srcHeight - 1 ? (srcHeight - 1).toDouble() : fy);
    final y0 = clampedY.floor();
    final y1 = y0 + 1 < srcHeight ? y0 + 1 : y0;
    final wy = clampedY - y0;
    final wyInv = 1.0 - wy;

    final row0Offset = y0 * srcRowBytes;
    final row1Offset = y1 * srcRowBytes;
    final dstRowOffset = targetY * inputSize;

    for (var dx = 0; dx < dstWidth; dx++) {
      final targetX = padLeft + dx;
      if (targetX < 0 || targetX >= inputSize) continue;

      final x0 = x0List[dx];
      final x1 = x1List[dx];
      final wx = wxList[dx];
      final wxInv = 1.0 - wx;

      final i00 = row0Offset + x0;
      final i01 = row0Offset + x1;
      final i10 = row1Offset + x0;
      final i11 = row1Offset + x1;

      final w00 = wyInv * wxInv;
      final w01 = wyInv * wx;
      final w10 = wy * wxInv;
      final w11 = wy * wx;

      final r = w00 * rgbBytes[i00] +
          w01 * rgbBytes[i01] +
          w10 * rgbBytes[i10] +
          w11 * rgbBytes[i11];
      final g = w00 * rgbBytes[i00 + 1] +
          w01 * rgbBytes[i01 + 1] +
          w10 * rgbBytes[i10 + 1] +
          w11 * rgbBytes[i11 + 1];
      final b = w00 * rgbBytes[i00 + 2] +
          w01 * rgbBytes[i01 + 2] +
          w10 * rgbBytes[i10 + 2] +
          w11 * rgbBytes[i11 + 2];

      final outIdx = dstRowOffset + targetX;
      tensor[outIdx] = r * inv255;
      tensor[gPlaneOffset + outIdx] = g * inv255;
      tensor[bPlaneOffset + outIdx] = b * inv255;
    }
  }

  return tensor;
}
