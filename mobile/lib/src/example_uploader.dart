import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:http/http.dart' as http;

import 'card_picture.dart';
import 'cards.dart';

const String examplesPath = '/api/v1/examples';
const Duration uploadTimeout = Duration(seconds: 30);

/// Why an example could not be sent, in words for the player.
class UploadException implements Exception {
  const UploadException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Sends the frame of a round away as a training example. The app keeps none.
abstract interface class ExampleUploader {
  /// Sends [frame] with the card it really shows. Throws an
  /// [UploadException] when the example was not taken in.
  Future<void> upload(RoundFrame frame, CardFace trueCard);
}

/// What the inbox is told about an example.
///
/// The names are a contract with the inbox and with `innersight pull`;
/// `server/contract/example.json` is the sample that all three are tested
/// against.
Map<String, Object> describeExample(RoundFrame frame, CardFace trueCard) {
  final detection = frame.card.detection;
  return {
    'rank': trueCard.rank,
    'color': trueCard.color.value,
    'box': {
      'x1': detection.box.x1,
      'y1': detection.box.y1,
      'x2': detection.box.x2,
      'y2': detection.box.y2,
    },
    'frame_width': frame.width,
    'frame_height': frame.height,
    'read_rank': detection.rank,
    'read_color': frame.card.color.value,
    'confidence': detection.confidence,
  };
}

/// Uploads examples to the inbox on the player's own server.
class HttpExampleUploader implements ExampleUploader {
  HttpExampleUploader({
    required this.server,
    required this.token,
    this.client,
    this.encode = encodePng,
  });

  /// The address of the inbox, such as `https://inbox.example.com`.
  final Uri server;

  /// The upload token of the inbox. It can add examples and nothing else.
  final String token;

  /// Packs the frame as the file that is sent.
  final Future<Uint8List> Function(CardPicture picture) encode;

  /// Sends the request. Without one, every upload opens a client of its own
  /// and closes it.
  final http.Client? client;

  @override
  Future<void> upload(RoundFrame frame, CardFace trueCard) async {
    final request = http.MultipartRequest('POST', server.resolve(examplesPath))
      ..headers['Authorization'] = 'Bearer $token'
      ..fields['metadata'] = jsonEncode(describeExample(frame, trueCard))
      ..files.add(
        http.MultipartFile.fromBytes(
          'image',
          await encode(frame.picture),
          filename: 'frame.png',
        ),
      );
    final response = await _send(request);
    if (response.statusCode != 201) {
      throw UploadException(_describeFailure(response));
    }
  }

  Future<http.Response> _send(http.MultipartRequest request) async {
    try {
      final sending = client?.send(request) ?? request.send();
      return await http.Response.fromStream(
        await sending.timeout(uploadTimeout),
      );
    } on http.ClientException catch (error) {
      debugPrint('Upload to $server failed: $error');
      throw const UploadException('The server could not be reached.');
    } on TimeoutException {
      throw const UploadException('The server did not answer in time.');
    }
  }
}

/// What the inbox said went wrong, or the status alone when the answer is not
/// its own, as when the server in front of it refuses the request.
String _describeFailure(http.Response response) {
  try {
    if (jsonDecode(response.body) case {
      'error': {'message': final String message},
    }) {
      return message;
    }
  } on FormatException {
    // Not an answer from the inbox; the status tells what there is to tell.
  }
  return 'The server answered ${response.statusCode}.';
}
