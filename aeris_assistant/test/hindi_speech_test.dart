import 'package:aeris_assistant/brain/executor.dart';
import 'package:aeris_assistant/brain/router.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:aeris_assistant/voice/hindi_speech.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  group('Hindi numbers', () {
    test('irregular 0–99', () {
      expect(hindiNumber(6), 'छह');
      expect(hindiNumber(25), 'पच्चीस');
      expect(hindiNumber(82), 'बयासी');
      expect(hindiNumber(99), 'निन्यानवे');
    });
    test('hundreds / thousands', () {
      expect(hindiNumber(100), 'एक सौ');
      expect(hindiNumber(1500), 'एक हज़ार पाँच सौ');
    });
  });

  group('times, the way people say them', () {
    test('6:30 AM → सुबह साढ़े छह बजे', () => expect(hindiTime(6, 30), 'सुबह साढ़े छह बजे'));
    test('7:15 → सवा सात', () => expect(hindiTime(7, 15), 'सुबह सवा सात बजे'));
    test('7:45 → पौने आठ', () => expect(hindiTime(7, 45), 'सुबह पौने आठ बजे'));
    test('1:30 → डेढ़', () => expect(hindiTime(13, 30), 'दोपहर डेढ़ बजे'));
    test('2:30 → ढाई', () => expect(hindiTime(14, 30), 'दोपहर ढाई बजे'));
    test('9:04 PM', () => expect(hindiTime(21, 4), 'रात नौ बजकर चार मिनट'));
    test('19:00', () => expect(hindiTime(19, 0), 'शाम सात बजे'));
  });

  group('full replies (what the voice actually reads)', () {
    test('alarm reply', () {
      expect(toSpokenDevanagari('6:30 a.m. ka alarm laga diya.'), 'सुबह साढ़े छह बजे का अलार्म लगा दिया।');
      expect(toSpokenDevanagari('Abhi 9:04 p.m. ho rahe hain.'), 'अभी रात नौ बजकर चार मिनट हो रहे हैं।');
      expect(toSpokenDevanagari('6:30 AM ka alarm.'), 'सुबह साढ़े छह बजे का अलार्म।'); // old style still read right
      // phone check 2026-11-17: "subah" must not be said twice
      expect(toSpokenDevanagari('Kal subah 6:30 a.m. ka alarm laga diya.'), 'कल सुबह साढ़े छह बजे का अलार्म लगा दिया।');
    });
    test('battery reply', () {
      expect(toSpokenDevanagari('Battery 82% hai.'), 'बैटरी बयासी परसेंट है।');
    });
    test('greeting with a name', () {
      expect(toSpokenDevanagari('Haan Shivang, boliye.'), 'हाँ शिवांग, बोलिए।');
    });
    test('names fall back to phonetics', () {
      expect(phonetic('Ravi'), 'रवि');
      expect(phonetic('Sharma'), 'शर्मा');
      expect(phonetic('Priya'), 'प्रिया');
    });
    test('phone numbers are read digit by digit', () {
      expect(toSpokenDevanagari('9876543210'), 'नौ आठ सात छह पाँच चार तीन दो एक शून्य');
    });
    test('every reply AERIS can give converts without Latin letters left', () async {
      final store = Store.memory()..settings = const Settings(onboarded: true);
      final exec = Executor(FakePhone(), store);
      const r = <String>[
        'time', 'date', 'battery', 'thanks', 'help', 'who', 'howareyou', 'end', 'greet',
      ];
      for (final tool in r) {
        final o = await exec.run(_plan(tool));
        final spoken = toSpokenDevanagari(o.reply);
        expect(RegExp(r'[A-Za-z]').hasMatch(spoken), isFalse, reason: '$tool: "${o.reply}" → "$spoken"');
      }
    });
  });

  group('male voice speaks masculine Hindi', () {
    test('JARVIS (default) → "raha hoon"', () async {
      final store = Store.memory()..settings = const Settings(onboarded: true);
      final o = await Executor(FakePhone(), store).run(_plan('open', {'app': 'youtube', 'target': 'com.google.android.youtube'}));
      expect(o.reply, 'Youtube khol raha hoon.');
    });
  });
}

Plan _plan(String tool, [Map<String, Object?> args = const {}]) => Plan(tool, args);
