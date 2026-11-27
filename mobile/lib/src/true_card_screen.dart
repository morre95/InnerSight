import 'package:flutter/material.dart';

import 'card_overlay.dart';
import 'card_picture.dart';
import 'cards.dart';
import 'picture_view.dart';

/// The frame is shown no taller than this, so the choices stay in view.
const double maxFrameHeight = 320;

/// Lets the player set the card that the frame of a round really shows.
///
/// It starts at the card the model read. Pops with the true card when the
/// player sends it, and with nothing when they go back.
class TrueCardScreen extends StatefulWidget {
  const TrueCardScreen({super.key, required this.frame, required this.config});

  final RoundFrame frame;
  final ModelConfig config;

  @override
  State<TrueCardScreen> createState() => _TrueCardScreenState();
}

class _TrueCardScreenState extends State<TrueCardScreen> {
  late String _rank = widget.frame.card.detection.rank;

  /// The color last chosen. It counts only for a rank in the four colors.
  late CardColor _suit = suitColors.contains(widget.frame.card.color)
      ? widget.frame.card.color
      : suitColors.first;

  CardFace get _trueCard {
    return CardFace(
      color: widget.config.fixedColor(_rank) ?? _suit,
      rank: _rank,
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final trueCard = _trueCard;
    final hasFixedColor = widget.config.fixedColor(_rank) != null;
    return Scaffold(
      appBar: AppBar(title: const Text('Set the true card')),
      // The button stays in view below the choices, which scroll.
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _buildFrame(),
                  const SizedBox(height: 12),
                  Text(
                    'True card: ${trueCard.label}',
                    style: textTheme.titleLarge,
                  ),
                  Text(
                    'Go back without sending if the outline does not fit '
                    'the card.',
                    style: textTheme.bodySmall,
                  ),
                  const SizedBox(height: 12),
                  Text('Color', style: textTheme.titleSmall),
                  Wrap(
                    spacing: 8,
                    children: [
                      for (final color in suitColors)
                        ChoiceChip(
                          label: Text(color.value),
                          selected: trueCard.color == color,
                          onSelected: hasFixedColor
                              ? null
                              : (_) => setState(() {
                                  _suit = color;
                                }),
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text('Rank', style: textTheme.titleSmall),
                  Wrap(
                    spacing: 8,
                    children: [
                      for (final rank in widget.config.ranks)
                        ChoiceChip(
                          label: Text(rank),
                          selected: _rank == rank,
                          onSelected: (_) => setState(() {
                            _rank = rank;
                          }),
                        ),
                    ],
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: FilledButton.icon(
                onPressed: () => Navigator.of(context).pop(trueCard),
                icon: const Icon(Icons.cloud_upload),
                label: const Text('Send'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// The whole frame, with the card outlined as the model read it.
  Widget _buildFrame() {
    final frame = widget.frame;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: maxFrameHeight),
        child: AspectRatio(
          aspectRatio: frame.width / frame.height,
          child: Stack(
            fit: StackFit.expand,
            children: [
              PictureView(picture: frame.picture),
              CustomPaint(
                painter: CardOverlayPainter(
                  cards: [frame.card],
                  frameWidth: frame.width,
                  frameHeight: frame.height,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
