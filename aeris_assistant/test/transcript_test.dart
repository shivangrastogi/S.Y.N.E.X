import 'package:aeris_assistant/brain/router.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/voice/local/local_mouth.dart';
import 'package:aeris_assistant/voice/translit.dart';
import 'package:flutter_test/flutter_test.dart';

/// What the on-device recognizer really wrote (tool/model_export eval,
/// 2026-11-16) → what the router must still understand.
void main() {
  const r = Router();
  String tool(String heard) => r.route(cleanTranscript(heard), now: DateTime(2026, 11, 16, 21)).tool;

  group('real transcripts from the on-device Hinglish model', () {
    final cases = <String, String>{
      'Kal subah 06:30 ka alarm laga do.': 'alarm',
      'Ravi ko WhatsApp karo ki main late hoon.': 'message',
      'Tour on karo.': 'torch',
      'Touch band karo.': 'torch',
      'Toarch bank karo': 'torch',
      'Bus': 'end',
      'bus bus': 'end',
      'Shaam 7 baje ka aalaan': 'alarm',
      'Papa ko message bhejon ki 5 minute mein aa raha hoon': 'message',
      'Papa ko message bhairjo ki 5 minute mein aa raha hoon': 'message',
      'Yahaan rakho ki meri car B2 mein parked hai': 'remember',
      'Battery kitni hai?': 'battery',
      'Meri car kahaan park ki thi.': 'search', // no memory given here → falls to search offer
      '10 minute ka timer lagao.': 'timer',
      'YouTube kholo.': 'open',
      'Mummy ko call karo.': 'call',
    };
    for (final e in cases.entries) {
      test('"${e.key}" → ${e.value}', () => expect(tool(e.key), e.value));
    }
  });

  group('corrections stay in their lane', () {
    test('"touch" alone is not torch', () {
      expect(cleanTranscript('touch screen kaam nahi kar rahi'), 'touch screen kaam nahi kar rahi');
    });
    test('"bus" inside a sentence stays a bus', () {
      expect(cleanTranscript('bus stand kahan hai'), 'bus stand kahan hai');
    });
    test('"of" is not turned into "off"', () {
      expect(cleanTranscript('20 percent of 500'), '20 percent of 500');
    });
    test('torch off survives', () => expect(cleanTranscript('Tour off karo'), 'torch off karo'));
    test('one-letter slips snap to the command word', () {
      expect(cleanTranscript('whatsap kholo'), 'whatsapp kholo');
      expect(cleanTranscript('batery kitni hai'), 'battery kitni hai');
    });
  });

  group('Devanagari → Hinglish', () {
    test('a full command', () {
      expect(romanize('कल सुबह का अलार्म लगा दो'), 'kal subah ka alarm laga do');
    });
    test('loanwords come back as English', () {
      expect(cleanTranscript('टॉर्च ऑन करो'), 'torch on karo');
    });
    test('Latin text passes through', () => expect(romanize('open WhatsApp'), 'open WhatsApp'));
  });

  group('JARVIS voice helpers', () {
    test('"a.m." never splits a sentence', () {
      final s = LocalMouth.sentences('Abhi 12:46 a.m. ho rahe hain. Aur kuch?');
      expect(s.map((e) => e.$2.trim()).toList(), ['Abhi 12:46 a.m. ho rahe hain.', 'Aur kuch?']);
    });
    test('sentences keep their offsets', () {
      final s = LocalMouth.sentences('Alarm set. Sleep well!');
      expect(s.length, 2);
      expect(s[1].$1, 10);
      expect(s[1].$2.trim(), 'Sleep well!');
    });
    test('word times are increasing and map to the full text', () {
      const text = 'Alarm set. Sleep well!';
      final s = LocalMouth.sentences(text)[1];
      final w = LocalMouth.wordTimes(s.$2, s.$1, 1000);
      expect(w.length, 2);
      expect(w[0].$1 < w[1].$1, isTrue);
      expect(text.substring(w[0].$2, w[0].$3), 'Sleep');
    });
  });

  test('old saved settings migrate to the own stack', () {
    final s = Settings.fromJson({'name': 'Shivang', 'voice': 'en-IN-NeerjaNeural', 'onb': true});
    expect(s.voice, 'jarvis');
    expect(s.stt, SttEngine.aeris);
    final kept = Settings.fromJson({'voice': 'en-IN-NeerjaNeural', 'stt': 'google'});
    expect(kept.voice, 'jarvis'); // one voice only: any old choice moves to JARVIS
    expect(kept.stt, SttEngine.google); // the listening choice is still respected
  });
}
