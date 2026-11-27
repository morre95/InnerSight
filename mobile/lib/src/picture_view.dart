import 'dart:async';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'card_picture.dart';

/// Shows a [CardPicture], scaled to fit the space it is given.
class PictureView extends StatefulWidget {
  const PictureView({super.key, required this.picture});

  final CardPicture picture;

  @override
  State<PictureView> createState() => _PictureViewState();
}

class _PictureViewState extends State<PictureView> {
  ui.Image? _image;

  @override
  void initState() {
    super.initState();
    unawaited(decodePicture(widget.picture).then(_onDecoded));
  }

  void _onDecoded(ui.Image image) {
    if (!mounted) {
      image.dispose();
      return;
    }
    setState(() {
      _image = image;
    });
  }

  @override
  void dispose() {
    _image?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RawImage(image: _image, fit: BoxFit.contain);
  }
}

/// Shows the picture of a card in a small box in the upright shape of a card.
class CardPictureView extends StatelessWidget {
  const CardPictureView({super.key, required this.picture});

  final CardPicture picture;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 40,
      height: 56,
      child: PictureView(picture: picture),
    );
  }
}
