import 'package:aeris_assistant/brain/parse.dart';
import 'package:aeris_assistant/brain/router.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:flutter_test/flutter_test.dart';

/// The routing contract: one owner per phrase. Add the phrase AND its
/// over-catch traps here whenever a rule changes.
void main() {
  const r = Router();
  final now = DateTime(2026, 11, 16, 21, 4); // 9:04 PM
  Plan route(String s, {List<Protocol> protocols = const [], List<Memory> memories = const []}) =>
      r.route(s, protocols: protocols, memories: memories, now: now);

  group('tool ownership', () {
    final cases = <String, String>{
      // alarm
      'kal subah 6:30 ka alarm laga do': 'alarm',
      'Set an alarm for 7 am tomorrow': 'alarm',
      'alarm 5:45 pe lagao': 'alarm',
      'mujhe 6 baje jaga dena': 'alarm',
      // timer
      '10 minute ka timer lagao': 'timer',
      'timer for 30 seconds': 'timer',
      'aadha ghanta ka timer': 'timer',
      // torch
      'torch on karo': 'torch',
      'flashlight band karo': 'torch',
      // message (approval)
      'Ravi ko WhatsApp karo ki main late hoon': 'message',
      'send a whatsapp to mom saying reached home': 'message',
      'Papa ko message bhejo ki 5 min mein aa raha hoon': 'message',
      // call
      'Mummy ko call karo': 'call',
      'call Ravi': 'call',
      '9876543210 pe call karo': 'call',
      // open app
      'YouTube kholo': 'open',
      'open whatsapp': 'open',
      'open google': 'open',
      'camera open karo': 'open',
      // search
      'search best biryani near me': 'search',
      'iphone 17 price google karo': 'search',
      // info
      'battery kitni hai': 'battery',
      'phone ki battery kitni hai': 'battery',
      'time kya hua': 'time',
      'what time is it': 'time',
      'aaj ki date kya hai': 'date',
      'what day is it today': 'date',
      // maths
      '12 into 8': 'math',
      '500 ka 20 percent': 'math',
      '100 divided by 4': 'math',
      // memory
      'yaad rakho ki meri car B2 mein parked hai': 'remember',
      'remember that the wifi password is tiger123': 'remember',
      // talk
      'hello': 'greet',
      'thank you': 'thanks',
      'tum kya kar sakti ho': 'help',
      'tum kaun ho': 'who',
      'kaise ho': 'howareyou',
      // end
      'bas': 'end',
      'bye': 'end',
      'ok bye': 'end',
    };
    for (final e in cases.entries) {
      test('"${e.key}" → ${e.value}', () => expect(route(e.key).tool, e.value));
    }
  });

  group('over-catch traps', () {
    test('a message mentioning time is still a message', () {
      expect(route('Ravi ko message karo ki main time pe aaunga').tool, 'message');
    });
    test('"phone ki battery" is not a call', () {
      expect(route('phone ki battery kitni hai').tool, 'battery');
    });
    test('"bas" inside a sentence does not end', () {
      expect(route('bas stop pe utar jaunga yaad rakho').tool, 'remember');
    });
    test('unknown → web search that asks first', () {
      final p = route('quantum entanglement samjhao');
      expect(p.tool, 'search');
      expect(p.needsApproval, isTrue);
    });
    test('message without text asks what to send', () {
      final p = route('Ravi ko whatsapp karo');
      expect(p.tool, 'clarify');
      expect(p.args['for'], 'message');
    });
    test('alarm without time asks when', () {
      expect(route('alarm laga do').tool, 'clarify');
    });
    test('bare "call karo" asks who', () {
      expect(route('call karo').tool, 'clarify');
    });
  });

  group('arguments', () {
    test('alarm keeps the exact time', () {
      final p = route('kal subah 6:30 ka alarm laga do');
      expect((p.args['hour'], p.args['minute']), (6, 30));
    });
    test('evening words make it PM', () {
      final p = route('shaam 7 baje ka alarm');
      expect((p.args['hour'], p.args['minute']), (19, 0));
    });
    test('message is split into who + body and needs approval', () {
      final p = route('Ravi ko WhatsApp karo ki main late hoon');
      expect(p.args['to'], 'ravi');
      expect(p.args['body'], 'main late hoon');
      expect(p.args['app'], 'whatsapp');
      expect(p.needsApproval, isTrue);
    });
    test('sms when not whatsapp', () {
      expect(route('Papa ko message bhejo ki 5 min mein aa raha hoon').args['app'], 'sms');
    });
    test('timer seconds', () {
      expect(route('1 ghanta 20 minute ka timer').args['seconds'], 4800);
    });
    test('torch off', () => expect(route('torch band karo').args['on'], isFalse));
    test('known app resolves to a package', () {
      expect(route('YouTube kholo').args['target'], 'com.google.android.youtube');
    });
    test('unknown app has no target', () => expect(route('zzapp kholo').args['target'], isNull));
    test('maths value', () => expect(route('12 into 8').args['value'], 96));
    test('remember keeps the user\'s own words, including case (phone bug, 2026-11-17)', () {
      expect(route('yaad rakho ki meri car B2 mein parked hai').args['text'], 'meri car B2 mein parked hai');
      expect(route('Remember that the WiFi password is Tiger123.').args['text'], 'the WiFi password is Tiger123');
      expect(route('Kal Ravi ka birthday hai yaad rakhna').args['text'], 'Kal Ravi ka birthday hai');
    });
  });

  group('protocols and recall', () {
    final protocols = [
      Protocol(id: 'w', name: 'Work', phrase: 'work mode on', actions: const ['torch off']),
      Protocol(id: 'x', name: 'Off', phrase: 'party mode', actions: const ['torch on'], enabled: false),
    ];
    test('phrase runs the protocol', () {
      final p = route('work mode on', protocols: protocols);
      expect(p.tool, 'protocol');
      expect(p.args['id'], 'w');
    });
    test('disabled protocol does not fire', () {
      expect(route('party mode', protocols: protocols).tool, isNot('protocol'));
    });
    test('"X kya hai" recalls a matching memory (phone bug, 2026-11-17)', () {
      final mems = [Memory(id: '1', text: 'gate code 4512B hai', createdAt: now)];
      final p = route('gate code kya hai', memories: mems);
      expect(p.tool, 'recall');
      expect(p.args['text'], 'gate code 4512B hai');
      // …but a "kya hai" with no shared words still goes elsewhere
      expect(route('quantum physics kya hai', memories: mems).tool, isNot('recall'));
      expect(route('time kya hai', memories: mems).tool, 'time');
    });
    test('recall finds the best memory', () {
      final mems = [
        Memory(id: '1', text: 'Wifi password is tiger123', createdAt: now),
        Memory(id: '2', text: 'Car is parked at B2 pillar 14', createdAt: now),
      ];
      final p = route('meri car kahan park ki thi', memories: mems);
      expect(p.tool, 'recall');
      expect(p.args['id'], '2');
    });
  });

  group('yes / no', () {
    test('haan', () => expect(yesNo('haan bhejo'), YesNo.yes));
    test('mat bhejo is a no even though it contains bhejo', () => expect(yesNo('mat bhejo'), YesNo.no));
    test('nahi', () => expect(yesNo('nahi rehne do'), YesNo.no));
    test('unrelated', () => expect(yesNo('weather kaisa hai'), YesNo.neither));
  });

  test('normalize keeps the verb "do" but maps "do minute"', () {
    expect(normalize('alarm laga do'), 'alarm laga do');
    expect(normalize('do minute ka timer'), '2 minute ka timer');
  });
}
