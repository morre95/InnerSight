import 'package:flutter/material.dart';

import 'collect_settings.dart';

/// The switch that turns collecting on, and with it on, where to send to.
class CollectSettingsFields extends StatefulWidget {
  const CollectSettingsFields({
    super.key,
    required this.settings,
    required this.onChanged,
  });

  final CollectSettings settings;
  final ValueChanged<CollectSettings> onChanged;

  @override
  State<CollectSettingsFields> createState() => _CollectSettingsFieldsState();
}

class _CollectSettingsFieldsState extends State<CollectSettingsFields> {
  late final TextEditingController _server = TextEditingController(
    text: widget.settings.server,
  );
  late final TextEditingController _token = TextEditingController(
    text: widget.settings.token,
  );

  @override
  void dispose() {
    _server.dispose();
    _token.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final settings = widget.settings;
    final hasUnsafeAddress =
        settings.server.trim().isNotEmpty && settings.serverUri == null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SwitchListTile(
          title: const Text('Collect misread cards'),
          subtitle: const Text(
            'After a game, send the cards the model read wrongly to your '
            'own server, to train on.',
          ),
          value: settings.isOn,
          onChanged: (isOn) => widget.onChanged(settings.copyWith(isOn: isOn)),
        ),
        if (settings.isOn) ...[
          TextField(
            controller: _server,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: InputDecoration(
              labelText: 'Server address',
              hintText: 'https://inbox.example.com',
              errorText: hasUnsafeAddress
                  ? 'The address must start with https://'
                  : null,
            ),
            onChanged: (server) =>
                widget.onChanged(settings.copyWith(server: server)),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _token,
            obscureText: true,
            autocorrect: false,
            enableSuggestions: false,
            decoration: const InputDecoration(labelText: 'Upload token'),
            onChanged: (token) =>
                widget.onChanged(settings.copyWith(token: token)),
          ),
          const SizedBox(height: 12),
        ],
      ],
    );
  }
}
