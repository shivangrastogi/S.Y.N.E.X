// English mode (lang.dart): common English phrasings must reach the same
// Tier-1 skills as their Hinglish twins, and English messaging commands must
// pull out the right contact + message.
import 'package:flutter_test/flutter_test.dart';
import 'package:aeris_remote/assistant/phone_agent.dart';
import 'package:aeris_remote/assistant/phone_skills.dart';

void main() {
  // command → owning skill (null = falls through to the cloud brain).
  const corpus = <String, String?>{
    'turn on the flashlight': 'torch',
    'turn off the torch': 'torch',
    'increase the volume': 'volume',
    'volume up': 'volume',
    'mute the phone': 'volume',
    'what time is it': 'datetime',
    "what's the date today": 'datetime',
    'what day is it': 'datetime',
    'battery percentage': 'battery',
    'how much battery is left': 'battery',
    'set an alarm for 7 am': 'alarm',
    'set a timer for 5 minutes': 'timer',
    'call mom': 'call',
    'send a whatsapp message to ravi saying hello': 'whatsapp',
    'send a text to mom saying I am late': 'sms',
    'open youtube': 'search',
    'open instagram': 'openApp',
    'search for cricket score on google': 'search',
    'play lofi music on youtube': 'search',
    'take a screenshot': 'screenshot',
    'go back': 'a11yGlobal',
    'go home': 'a11yGlobal',
    'open notifications': 'a11yGlobal',
    'scroll down': 'a11yScroll',
    'read the screen': 'a11yRead',
    'summarise this screen': 'a11ySummarise',
    'next song': 'media',
    'pause the music': 'media',
    'open wifi settings': 'settings',
    'turn on bluetooth': 'settings',
    'what is 25 percent of 400': 'math',
    'tap on settings': 'a11yTap',
    'click the send button': 'a11yTap',
    'press ok': 'a11yTap',
    'tell me a joke': null,
    'who is the prime minister of india': null,
  };

  group('English routing', () {
    corpus.forEach((phrase, expected) {
      test('"$phrase" → ${expected ?? "cloud"}', () {
        expect(PhoneSkills.firstMatch(phrase), expected,
            reason: 'matched: ${PhoneSkills.allMatches(phrase)}');
        // One-shot commands never cost a planner round-trip.
        expect(PhoneAgent.looksLikeTask(phrase), isFalse);
      });
    });
  });

  group('englishMessage', () {
    const wa = r'whats\s*app';
    const cases = <String, (String, String)?>{
      'send a whatsapp message to Ravi saying hello': ('ravi', 'hello'),
      'Send WhatsApp to my mom saying I will be late.':
          ('mom', 'I will be late'),
      'send a message to Ravi Kumar on WhatsApp that the meeting moved':
          ('ravi kumar', 'the meeting moved'),
      'message Ravi on whatsapp saying good morning': ('ravi', 'good morning'),
      'whatsapp Ravi saying call me': ('ravi', 'call me'),
      'Hey Aeris, send a whatsapp to Ravi': ('ravi', ''),
      // Hinglish shape is not English shape → null (old parser handles it).
      'ravi ko whatsapp pe hello bolo': null,
    };
    cases.forEach((raw, want) {
      test(raw, () => expect(PhoneSkills.englishMessage(raw, wa), want));
    });

    test('sms shapes', () {
      const sms = r'sms|text message|text';
      expect(PhoneSkills.englishMessage('send a text to mom saying hi', sms),
          ('mom', 'hi'));
      expect(PhoneSkills.englishMessage('text dad saying on my way', sms),
          ('dad', 'on my way'));
    });
  });

  group('spokenNumber', () {
    test('the 2026-10-17 failing command', () {
      const raw = 'I want to do send a WhatsApp message on this number '
          '7300 978845 hi';
      expect(PhoneSkills.firstMatch(raw), 'whatsapp');
      expect(PhoneSkills.spokenNumber(raw), ('7300978845', 'hi'));
    });
    test('grouped / prefixed numbers', () {
      expect(PhoneSkills.spokenNumber('+91 73009 78845 pe hello bhejo'),
          ('917300978845', 'hello bhejo'));
      expect(PhoneSkills.spokenNumber('send 98765-43210 saying on my way'),
          ('9876543210', 'on my way'));
    });
    test('short numbers and times are not phone numbers', () {
      expect(PhoneSkills.spokenNumber('set an alarm for 7 30'), isNull);
      expect(PhoneSkills.spokenNumber('what is 25 percent of 400'), isNull);
    });
  });
}
