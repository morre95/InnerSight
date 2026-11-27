import 'package:shared_preferences/shared_preferences.dart';

/// Whether the misread cards of a game are collected, and where they are sent.
class CollectSettings {
  const CollectSettings({this.isOn = false, this.server = '', this.token = ''});

  final bool isOn;

  /// The address of the inbox, as the player typed it.
  final String server;

  /// The upload token of the inbox, as the player typed it.
  final String token;

  /// Where the examples are sent, or null while [server] is not an address
  /// the app may send pictures to.
  Uri? get serverUri => parseServerAddress(server);

  /// True when collecting is turned on and there is somewhere to send to.
  bool get isReady => isOn && serverUri != null && token.trim().isNotEmpty;

  CollectSettings copyWith({bool? isOn, String? server, String? token}) {
    return CollectSettings(
      isOn: isOn ?? this.isOn,
      server: server ?? this.server,
      token: token ?? this.token,
    );
  }
}

/// The address as a URI, or null if pictures and the token must not be sent
/// there: it has to be an HTTPS address, so nobody on the way can read them.
///
/// A server on the same computer is allowed without HTTPS, to try an inbox
/// out with the web app.
Uri? parseServerAddress(String address) {
  final uri = Uri.tryParse(address.trim());
  if (uri == null || uri.host.isEmpty) {
    return null;
  }
  final isOnThisComputer = uri.host == 'localhost' || uri.host == '127.0.0.1';
  final isSafe =
      uri.isScheme('https') || (uri.isScheme('http') && isOnThisComputer);
  return isSafe ? uri : null;
}

/// Keeps the collect settings from one start of the app to the next.
abstract interface class CollectSettingsStore {
  Future<CollectSettings> load();

  Future<void> save(CollectSettings settings);
}

/// Keeps the settings in the preferences of the phone, or of the browser.
///
/// The token is kept there as it is. That is acceptable for the upload token,
/// which can add examples to the inbox and neither read nor remove them.
class PreferencesCollectSettingsStore implements CollectSettingsStore {
  static const String _isOnKey = 'collect.is_on';
  static const String _serverKey = 'collect.server';
  static const String _tokenKey = 'collect.token';

  final SharedPreferencesAsync _preferences = SharedPreferencesAsync();

  @override
  Future<CollectSettings> load() async {
    return CollectSettings(
      isOn: await _preferences.getBool(_isOnKey) ?? false,
      server: await _preferences.getString(_serverKey) ?? '',
      token: await _preferences.getString(_tokenKey) ?? '',
    );
  }

  @override
  Future<void> save(CollectSettings settings) async {
    await _preferences.setBool(_isOnKey, settings.isOn);
    await _preferences.setString(_serverKey, settings.server);
    await _preferences.setString(_tokenKey, settings.token);
  }
}
