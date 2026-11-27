import 'package:flutter_test/flutter_test.dart';
import 'package:innersight_mobile/src/collect_settings.dart';
import 'package:shared_preferences_platform_interface/in_memory_shared_preferences_async.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_async_platform_interface.dart';

const _ready = CollectSettings(
  isOn: true,
  server: 'https://inbox.example',
  token: 'an-upload-token',
);

void main() {
  group('parseServerAddress', () {
    test('takes an https address', () {
      expect(
        parseServerAddress(' https://inbox.example '),
        Uri.parse('https://inbox.example'),
      );
    });

    test('refuses a server address that is not https', () {
      expect(parseServerAddress('http://inbox.example'), isNull);
    });

    test('takes a server on this computer without https', () {
      expect(parseServerAddress('http://localhost:8000'), isNotNull);
    });

    test('refuses what is not an address', () {
      expect(parseServerAddress(''), isNull);
      expect(parseServerAddress('inbox.example'), isNull);
    });
  });

  group('CollectSettings', () {
    test('is ready when it is on and has an address and a token', () {
      expect(_ready.isReady, isTrue);
    });

    test('is not ready while it is turned off', () {
      expect(_ready.copyWith(isOn: false).isReady, isFalse);
    });

    test('is not ready without a safe address or without a token', () {
      expect(_ready.copyWith(server: 'http://inbox.example').isReady, isFalse);
      expect(_ready.copyWith(token: ' ').isReady, isFalse);
    });
  });

  group('PreferencesCollectSettingsStore', () {
    setUp(() {
      SharedPreferencesAsyncPlatform.instance =
          InMemorySharedPreferencesAsync.empty();
    });

    test('has collecting turned off before anything is saved', () async {
      final settings = await PreferencesCollectSettingsStore().load();

      expect(settings.isOn, isFalse);
      expect((settings.server, settings.token), ('', ''));
    });

    test('remembers the settings until the app is started again', () async {
      await PreferencesCollectSettingsStore().save(_ready);

      final settings = await PreferencesCollectSettingsStore().load();

      expect(settings.isOn, isTrue);
      expect(settings.server, 'https://inbox.example');
      expect(settings.token, 'an-upload-token');
    });
  });
}
