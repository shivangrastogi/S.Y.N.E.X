// Prints what the JARVIS voice will actually read for some real replies.
import 'dart:convert';
import 'dart:io';

import 'package:aeris_assistant/voice/hindi_speech.dart';

void main() {
  const replies = [
    'Haan Shivang, boliye.',
    '6:30 AM ka alarm laga diya.',
    'Battery 82% hai, charging ho rahi hai.',
    'Abhi 9:04 PM ho rahe hain.',
    'Youtube khol raha hoon.',
    'Main AERIS hoon, aapka assistant. Isi phone pe chalta hoon.',
  ];
  stdout.write(jsonEncode([for (final r in replies) [r, toSpokenDevanagari(r)]]));
}
