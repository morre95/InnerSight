import 'dart:async';

import 'package:flutter/material.dart';

import 'card_overlay.dart';
import 'card_picture.dart';
import 'cards.dart';
import 'guessing.dart';
import 'picture_view.dart';
import 'round_collector.dart';
import 'true_card_screen.dart';

/// Shows how a guessing session went: the count of every outcome, then every
/// card with its picture and how sure the model was when it read it.
///
/// With a [collector], a round can be tapped to set its true card and send
/// its frame away as a training example.
class ResultBoard extends StatelessWidget {
  const ResultBoard({
    super.key,
    required this.rounds,
    required this.pictures,
    required this.onDone,
    this.collector,
  });

  final List<GuessRound> rounds;

  /// The picture of the card of every round, in the order of [rounds].
  final List<CardPicture> pictures;
  final VoidCallback onDone;

  /// Holds the frame of every round, in the order of [rounds], when the
  /// misread cards are collected.
  final RoundCollector? collector;

  Future<void> _setTrueCard(
    BuildContext context,
    RoundCollector collector,
    int index,
  ) async {
    final trueCard = await Navigator.of(context).push<CardFace>(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => TrueCardScreen(
          frame: collector.frameOf(index),
          config: collector.config,
        ),
      ),
    );
    if (trueCard != null) {
      unawaited(collector.send(index, trueCard));
    }
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final counts = countOutcomes(rounds);
    final collector = this.collector;
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
            if (collector != null) ...[
              Text(
                'Tap a card the model read wrongly to send it to your server.',
                style: textTheme.bodySmall,
              ),
              const SizedBox(height: 4),
            ],
            Expanded(
              child: Card(
                child: ListView.builder(
                  itemCount: rounds.length,
                  itemBuilder: (context, index) => _RoundTile(
                    number: index + 1,
                    round: rounds[index],
                    picture: pictures[index],
                    collector: collector,
                    onSetTrueCard: collector == null
                        ? null
                        : () => _setTrueCard(context, collector, index),
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
    required this.collector,
    required this.onSetTrueCard,
  });

  final int number;
  final GuessRound round;
  final CardPicture picture;
  final RoundCollector? collector;
  final VoidCallback? onSetTrueCard;

  @override
  Widget build(BuildContext context) {
    final collector = this.collector;
    if (collector == null) {
      return _buildTile(context, status: null, error: null);
    }
    return ListenableBuilder(
      listenable: collector,
      builder: (context, _) => _buildTile(
        context,
        status: collector.statusOf(number - 1),
        error: collector.errorOf(number - 1),
      ),
    );
  }

  /// The tile of the round. With a [status], it also shows how far the frame
  /// of the round has come, and can be tapped until the frame is sent.
  Widget _buildTile(
    BuildContext context, {
    required SendStatus? status,
    required String? error,
  }) {
    final canBeSent =
        status == SendStatus.notSent || status == SendStatus.failed;
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
      subtitle: error != null
          ? Text(
              error,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            )
          : Text('Model ${_percent(round.confidence)} sure'),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(round.outcome.phrase),
          if (status != null) ...[
            const SizedBox(width: 8),
            _SendStatusIcon(status: status),
          ],
        ],
      ),
      onTap: canBeSent ? onSetTrueCard : null,
    );
  }
}

class _SendStatusIcon extends StatelessWidget {
  const _SendStatusIcon({required this.status});

  final SendStatus status;

  @override
  Widget build(BuildContext context) {
    return switch (status) {
      SendStatus.notSent => const Tooltip(
        message: 'Send as a training example',
        child: Icon(Icons.cloud_upload_outlined),
      ),
      SendStatus.sending => const Tooltip(
        message: 'Sending',
        child: SizedBox.square(
          dimension: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      SendStatus.sent => const Tooltip(
        message: 'Sent',
        child: Icon(Icons.cloud_done),
      ),
      SendStatus.failed => Tooltip(
        message: 'Not sent. Tap to try again',
        child: Icon(
          Icons.error_outline,
          color: Theme.of(context).colorScheme.error,
        ),
      ),
    };
  }
}

String _percent(double fraction) => '${(fraction * 100).round()}%';
