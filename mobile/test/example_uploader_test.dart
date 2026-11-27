import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:innersight_mobile/src/card_picture.dart';
import 'package:innersight_mobile/src/cards.dart';
import 'package:innersight_mobile/src/example_uploader.dart';

const _uploadToken = 'an-upload-token';
const _trueCard = CardFace(color: CardColor.red, rank: '9');
final _server = Uri.parse('https://inbox.example');
final _pngBytes = Uint8List.fromList([137, 80, 78, 71]);

/// A frame as in `server/contract/example.json`: read as a red 6.
RoundFrame _contractFrame() {
  const width = 480;
  const height = 720;
  return RoundFrame(
    rgbBytes: Uint8List(width * height * 3),
    width: width,
    height: height,
    card: const RecognizedCard(
      detection: Detection(
        rank: '6',
        confidence: 0.62,
        box: Box(x1: 120, y1: 200, x2: 360, y2: 560),
      ),
      color: CardColor.red,
    ),
  );
}

HttpExampleUploader _uploaderWith(MockClient client) {
  return HttpExampleUploader(
    server: _server,
    token: _uploadToken,
    client: client,
    encode: (picture) async => _pngBytes,
  );
}

http.Response _refusal(int statusCode, String message) {
  return http.Response(
    jsonEncode({
      'success': false,
      'error': {'code': 'SOME_CODE', 'message': message},
    }),
    statusCode,
  );
}

void main() {
  group('describeExample', () {
    test('describes the example as the shared contract file does', () {
      final contract = jsonDecode(
        File('../server/contract/example.json').readAsStringSync(),
      );

      expect(describeExample(_contractFrame(), _trueCard), contract);
    });
  });

  group('HttpExampleUploader', () {
    test('sends the example to the inbox with the upload token', () async {
      late http.Request sent;
      final client = MockClient((request) async {
        sent = request;
        return http.Response('{"success": true}', 201);
      });

      await _uploaderWith(client).upload(_contractFrame(), _trueCard);

      expect(sent.method, 'POST');
      expect(sent.url, Uri.parse('https://inbox.example/api/v1/examples'));
      expect(sent.headers['Authorization'], 'Bearer $_uploadToken');
    });

    test('sends the frame as a picture and what is told about it', () async {
      late String body;
      final client = MockClient((request) async {
        body = latin1.decode(request.bodyBytes);
        return http.Response('{"success": true}', 201);
      });

      await _uploaderWith(client).upload(_contractFrame(), _trueCard);

      expect(body, contains('name="image"; filename="frame.png"'));
      expect(body, contains(latin1.decode(_pngBytes)));
      expect(body, contains('name="metadata"'));
      expect(body, contains('"rank":"9"'));
      expect(body, contains('"read_rank":"6"'));
    });

    test('tells what the inbox said when it refuses the token', () async {
      final client = MockClient(
        (request) async => _refusal(401, 'The token is not valid'),
      );

      expect(
        _uploaderWith(client).upload(_contractFrame(), _trueCard),
        throwsA(
          isA<UploadException>().having(
            (error) => error.message,
            'message',
            'The token is not valid',
          ),
        ),
      );
    });

    test('tells the status when the answer is not from the inbox', () async {
      final client = MockClient(
        (request) async => http.Response('Content Too Large', 413),
      );

      expect(
        _uploaderWith(client).upload(_contractFrame(), _trueCard),
        throwsA(
          isA<UploadException>().having(
            (error) => error.message,
            'message',
            'The server answered 413.',
          ),
        ),
      );
    });

    test('tells when the server could not be reached', () async {
      final client = MockClient(
        (request) async => throw http.ClientException('connection refused'),
      );

      expect(
        _uploaderWith(client).upload(_contractFrame(), _trueCard),
        throwsA(
          isA<UploadException>().having(
            (error) => error.message,
            'message',
            'The server could not be reached.',
          ),
        ),
      );
    });
  });

  group('RoundFrame', () {
    test('gives the whole frame as a picture', () {
      final frame = RoundFrame(
        rgbBytes: Uint8List.fromList([1, 2, 3, 4, 5, 6]),
        width: 2,
        height: 1,
        card: _contractFrame().card,
      );

      final picture = frame.picture;

      expect((picture.width, picture.height), (2, 1));
      expect(picture.rgbaBytes, [1, 2, 3, 255, 4, 5, 6, 255]);
    });
  });

  group('encodePng', () {
    testWidgets('packs a picture as a PNG file of the same size', (
      tester,
    ) async {
      final picture = CardPicture(
        rgbaBytes: Uint8List(2 * 3 * 4),
        width: 2,
        height: 3,
      );

      final png = (await tester.runAsync(() => encodePng(picture)))!;

      const signature = [137, 80, 78, 71, 13, 10, 26, 10];
      final header = ByteData.sublistView(png, 16, 24);
      expect(png.sublist(0, 8), signature);
      expect((header.getUint32(0), header.getUint32(4)), (2, 3));
    });
  });
}
