import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'card_overlay.dart';
import 'card_picture.dart';
import 'guessing.dart';

/// Shows how a guessing session went: the count of every outcome, then every
/// card with its picture and how sure the model was when it read it.
class ResultBoard extends StatelessWidget {
  const ResultBoard({
    super.key,
    required this.rounds,
    required this.pictures,
    required this.onDone,
  });

  final List<GuessRound> rounds;

  /// The picture of the card of every round, in the order of [rounds].
  final List<CardPicture> pictures;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final counts = countOutcomes(rounds);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Session result: ${rounds.length} cards',
              style: textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            Card(
              child: Column(
                children: [
                  for (final outcome in GuessOutcome.values)
                    ListTile(
                      dense: true,
                      title: Text(outcome.phrase),
                      trailing: Text(
                        '${counts[outcome]}   ${_percent(counts[outcome]! / rounds.length)}',
                        style: textTheme.titleMedium,
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Card(
                child: ListView.builder(
                  itemCount: rounds.length,
                  itemBuilder: (context, index) => _RoundTile(
                    number: index + 1,
                    round: rounds[index],
                    picture: pictures[index],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: onDone,
              icon: const Icon(Icons.check),
              label: const Text('Done'),
            ),
          ],
        ),
      ),
    );
  }
}

class _RoundTile extends StatelessWidget {
  const _RoundTile({
    required this.number,
    required this.round,
    required this.picture,
  });

  final int number;
  final GuessRound round;
  final CardPicture picture;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircleAvatar(
            radius: 14,
            backgroundColor: outlineColorFor(round.face.color),
            foregroundColor: Colors.black,
            child: Text('$number', style: const TextStyle(fontSize: 12)),
          ),
          const SizedBox(width: 12),
          CardPictureView(picture: picture),
        ],
      ),
      title: Text(round.face.label),
      subtitle: Text('Model ${_percent(round.confidence)} sure'),
      trailing: Text(round.outcome.phrase),
    );
  }
}

/// Shows a [CardPicture], scaled to fit a box in the upright shape of a card.
class CardPictureView extends StatefulWidget {
  const CardPictureView({super.key, required this.picture});

  final CardPicture picture;

  @override
  State<CardPictureView> createState() => _CardPictureViewState();
}

class _CardPictureViewState extends State<CardPictureView> {
  ui.Image? _image;

  @override
  void initState() {
    super.initState();
    final picture = widget.picture;
    ui.decodeImageFromPixels(
      picture.rgbaBytes,
      picture.width,
      picture.height,
      ui.PixelFormat.rgba8888,
      _onDecoded,
    );
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
    return SizedBox(
      width: 40,
      height: 56,
      child: RawImage(image: _image, fit: BoxFit.contain),
    );
  }
}

String _percent(double fraction) => '${(fraction * 100).round()}%';
