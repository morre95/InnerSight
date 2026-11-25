import 'package:flutter/material.dart';

import 'cards.dart';

/// Outline colors matching `OUTLINE_BGR` in `src/innersight/annotation.py`.
Color outlineColorFor(CardColor color) {
  return switch (color) {
    CardColor.red => const Color(0xFFFF1744),
    CardColor.yellow => const Color(0xFFFFEA00),
    CardColor.green => const Color(0xFF00C853),
    CardColor.blue => const Color(0xFF2979FF),
    CardColor.wild => const Color(0xFFFF00FF),
    CardColor.back => const Color(0xFFFFFFFF),
    CardColor.unknown => const Color(0xFF808080),
  };
}

/// Paints bounding boxes and labels for recognized cards on top of [CameraPreview].
class CardOverlayPainter extends CustomPainter {
  const CardOverlayPainter({
    required this.cards,
    required this.frameWidth,
    required this.frameHeight,
    this.mirrorHorizontal = false,
  });

  final List<RecognizedCard> cards;
  final int frameWidth;
  final int frameHeight;
  final bool mirrorHorizontal;

  @override
  void paint(Canvas canvas, Size size) {
    if (cards.isEmpty || frameWidth <= 0 || frameHeight <= 0) {
      return;
    }

    final scaleX = size.width / frameWidth;
    final scaleY = size.height / frameHeight;

    for (final card in cards) {
      final box = card.detection.box;
      final rawLeft = mirrorHorizontal
          ? (frameWidth - box.x2).toDouble()
          : box.x1.toDouble();
      final rawRight = mirrorHorizontal
          ? (frameWidth - box.x1).toDouble()
          : box.x2.toDouble();

      final rect = Rect.fromLTRB(
        rawLeft * scaleX,
        box.y1 * scaleY,
        rawRight * scaleX,
        box.y2 * scaleY,
      );

      final color = outlineColorFor(card.color);
      final boxPaint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3.0;
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(6)),
        boxPaint,
      );

      final confPct = (card.detection.confidence * 100).round();
      final textSpan = TextSpan(
        text: '${card.label} $confPct%',
        style: TextStyle(
          color: color,
          fontSize: 14,
          fontWeight: FontWeight.w700,
        ),
      );
      final textPainter = TextPainter(
        text: textSpan,
        textDirection: TextDirection.ltr,
      )..layout();

      const pillPaddingH = 8.0;
      const pillPaddingV = 4.0;
      final pillWidth = textPainter.width + pillPaddingH * 2;
      final pillHeight = textPainter.height + pillPaddingV * 2;
      final pillLeft = rect.left.clamp(
        0.0,
        (size.width - pillWidth).clamp(0.0, size.width),
      );
      final pillTop = rect.top - pillHeight - 4 >= 0
          ? rect.top - pillHeight - 4
          : rect.top + 4;

      final pillRect = RRect.fromRectAndRadius(
        Rect.fromLTWH(pillLeft, pillTop, pillWidth, pillHeight),
        const Radius.circular(6),
      );
      canvas.drawRRect(
        pillRect,
        Paint()..color = Colors.black.withValues(alpha: 0.78),
      );
      textPainter.paint(
        canvas,
        Offset(pillLeft + pillPaddingH, pillTop + pillPaddingV),
      );
    }
  }

  @override
  bool shouldRepaint(covariant CardOverlayPainter oldDelegate) {
    return oldDelegate.cards != cards ||
        oldDelegate.frameWidth != frameWidth ||
        oldDelegate.frameHeight != frameHeight ||
        oldDelegate.mirrorHorizontal != mirrorHorizontal;
  }
}
