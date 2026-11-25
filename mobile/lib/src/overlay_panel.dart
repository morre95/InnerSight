import 'package:flutter/material.dart';

/// Dark rounded panel that keeps text readable on top of the camera preview.
class OverlayPanel extends StatelessWidget {
  const OverlayPanel({
    super.key,
    required this.child,
    this.borderColor = Colors.white24,
  });

  final Widget child;
  final Color borderColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: borderColor, width: 1.5),
      ),
      child: child,
    );
  }
}
