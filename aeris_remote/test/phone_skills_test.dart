// Collision guard for Tier-1 phone skills (Phase A2).
//
// The contract: every representative command resolves to exactly the intended
// skill (first-match-wins), and plain questions fall through to the laptop.
// This is the phone twin of the laptop's pattern-unification guard.
import 'package:flutter_test/flutter_test.dart';
import 'package:aeris_remote/assistant/phone_agent.dart';
import 'package:aeris_remote/assistant/phone_skills.dart';

void main() {
  // command → owning skill (null = falls through to laptop/cloud brain).
  const corpus = <String, String?>{
    // torch
    'torch on karo': 'torch',
    'flashlight band karo': 'torch',
    'torch jala do': 'torch',
    'roshni band kar do': 'torch',
    // volume
    'volume badhao': 'volume',
    'awaaz kam karo': 'volume',
    'volume full karo': 'volume',
    'phone mute karo': 'volume',
    // alarm / timer
    'subah 7 baje alarm lagao': 'alarm',
    'raat 9 baje ka alarm set karo': 'alarm',
    '5 minute ka timer lagao': 'timer',
    '10 minute timer': 'timer',
    // whatsapp / sms / call
    'papa ko whatsapp pe bolo ghar aa jao': 'whatsapp',
    'rahul ko whatsapp message bhejo kaise ho': 'whatsapp',
    'mummy ko message bhejo aa raha hoon': 'sms',
    'rahul ko sms karo': 'sms',
    'mummy ko call karo': 'call',
    'papa ko phone lagao': 'call',
    'call rahul': 'call',
    '9876543210 ko call karo': 'call',
    // search / music
    'youtube pe lofi chalao': 'search',
    'google karo aaj ka mausam': 'search',
    'koi gaana chalao': 'search',
    'youtube pe cricket highlights dekho': 'search',
    // settings panels
    'wifi on karo': 'settings',
    'bluetooth on karo': 'settings',
    'brightness kam karo': 'settings',
    'do not disturb on karo': 'settings',
    'internet on karo': 'settings',
    // instant offline skills (Phase A9)
    'battery kitni hai': 'battery',
    'charging ho rahi hai kya': 'battery',
    'time kya hua hai': 'datetime',
    'aaj kaunsa din hai': 'datetime',
    '15 percent of 2000': 'math',
    '25 plus 75 kitna hota hai': 'math',
    'screenshot lo': 'screenshot',
    // media control (explicit verbs) vs search (new song)
    'gaana pause karo': 'media',
    'agla gaana': 'media',
    'pichla gana chalao': 'media',
    'music band karo': 'media',
    'gaana chalao': 'search',
    // screen control (Phase A5)
    'back jao': 'a11yGlobal',
    'home jao': 'a11yGlobal',
    'notification kholo': 'a11yGlobal',
    'recent apps kholo': 'a11yGlobal',
    'scroll karo': 'a11yScroll',
    'thoda neeche karo': 'a11yScroll',
    'screen padho': 'a11yRead',
    'screen pe kya likha hai': 'a11yRead',
    'is page ko summarise karo': 'a11ySummarise',
    'ye screen samjhao': 'a11ySummarise',
    'send button pe tap karo': 'a11yTap',
    'ok pe click karo': 'a11yTap',
    // open app (generic verb, last)
    'whatsapp kholo': 'openApp',
    'youtube kholo': 'openApp',
    'instagram open karo': 'openApp',
    'settings kholo': 'openApp',
    'camera chalu karo': 'openApp',
    'gpay kholo': 'openApp',
    // fall-through — NOT phone skills
    'aaj mausam kaisa hai': null,
    'tum kaise ho': null,
    'ek joke sunao': null,
    'newton ka teesra niyam batao': null,
    'meri agli meeting kab hai': null,
  };

  group('Tier-1 skill routing', () {
    corpus.forEach((phrase, expected) {
      test('"$phrase" → ${expected ?? "laptop/cloud"}', () {
        expect(PhoneSkills.firstMatch(phrase), expected,
            reason: 'matched: ${PhoneSkills.allMatches(phrase)}');
      });
    });
  });

  // Phase 10: the agent is offered a turn BEFORE Tier-1, so no one-shot
  // command may look like an agent task (it would pay a planner round-trip).
  test('no phrase in the corpus is taken by the phone agent', () {
    for (final phrase in corpus.keys) {
      expect(PhoneAgent.looksLikeTask(phrase), isFalse,
          reason: '"$phrase" is one-shot, not a multi-step task');
    }
  });

  test('no fall-through phrase is claimed by any skill', () {
    for (final e in corpus.entries) {
      if (e.value == null) {
        expect(PhoneSkills.allMatches(e.key), isEmpty,
            reason: '"${e.key}" should reach the laptop untouched');
      }
    }
  });
}
