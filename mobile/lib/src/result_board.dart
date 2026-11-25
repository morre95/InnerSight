import 'package:flutter/material.dart';

import 'card_overlay.dart';
import 'guessing.dart';

/// Shows how a guessing session went: the count of every outcome, then every
/// card with how sure the model was when it read it.
class ResultBoard extends StatelessWidget {
  const ResultBoard({super.key, required this.rounds, required this.onDone});

  final List<GuessRound> rounds;
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
                  itemBuilder: (context, index) =>
                      _RoundTile(number: index + 1, round: rounds[index]),
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
  const _RoundTile({required this.number, required this.round});

  final int number;
  final GuessRound round;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      dense: true,
      leading: CircleAvatar(
        radius: 14,
        backgroundColor: outlineColorFor(round.face.color),
        foregroundColor: Colors.black,
        child: Text('$number', style: const TextStyle(fontSize: 12)),
      ),
      title: Text(round.face.label),
      subtitle: Text('Model ${_percent(round.confidence)} sure'),
      trailing: Text(round.outcome.phrase),
    );
  }
}

String _percent(double fraction) => '${(fraction * 100).round()}%';
