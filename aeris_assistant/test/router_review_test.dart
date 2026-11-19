import 'package:aeris_assistant/brain/parse.dart';
import 'package:aeris_assistant/brain/router.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:flutter_test/flutter_test.dart';

/// Every bug found in the 2026-11-17 review, as a sentence a real person
/// says — plus the neighbours each fix must leave alone.
void main() {
  const r = Router();
  final morning = DateTime(2026, 11, 17, 7, 0); // 7:00 am
  final night = DateTime(2026, 11, 17, 22, 0); // 10:00 pm
  final defaults = Store.defaultProtocols().map((p) => p.copyWith(enabled: true)).toList();
  Plan route(String s, {DateTime? now, List<Protocol> protocols = const []}) =>
      r.route(s, now: now ?? morning, protocols: protocols);

  group('approval replies (yes / no)', () {
    test('a trailing "na" is a softener, not a no', () {
      expect(yesNo('haan na'), YesNo.yes);
      expect(yesNo('haan bhej do na'), YesNo.yes);
      expect(yesNo('bhejo na'), YesNo.yes);
      expect(yesNo('han ji bilkul'), YesNo.yes);
      expect(yesNo('haan google pe dekho'), YesNo.yes);
    });
    test('a leading "na" is a no', () {
      expect(yesNo('na'), YesNo.no);
      expect(yesNo('na rehne do'), YesNo.no);
      expect(yesNo('ok mat bhejo'), YesNo.no);
      expect(yesNo('nahi ruko'), YesNo.no);
    });
    test('a new command is not a yes, even with "karo" in it', () {
      expect(yesNo('papa ko call karo'), YesNo.neither);
      expect(yesNo('kuch aur karo'), YesNo.neither);
      expect(yesNo('alarm laga do'), YesNo.neither);
    });
  });

  group('protocols need their phrase, not just a mention of it', () {
    test('the phrase (with filler) runs it', () {
      expect(route('focus mode', protocols: defaults).tool, 'protocol');
      expect(route('focus mode on karo', protocols: defaults).tool, 'protocol');
      expect(route('start focus mode', protocols: defaults).tool, 'protocol');
      expect(route('good morning aeris', protocols: defaults).tool, 'protocol');
    });
    test('turning it off or using it in a sentence does not', () {
      expect(route('focus mode band karo', protocols: defaults).tool, isNot('protocol'));
      expect(route('good morning message mummy ko bhejo', protocols: defaults).tool, isNot('protocol'));
    });
  });

  group('alarms', () {
    test('"for 5 minutes" is 5 minutes from now, not 5 PM', () {
      final p = route('alarm for 5 minutes');
      expect(p.tool, 'alarm');
      expect((p.args['hour'], p.args['minute']), (7, 5));
    });
    test('relative alarms', () {
      expect(route('wake me up in 20 minutes').args['minute'], 20);
      expect(route('20 minute baad alarm laga do').args['minute'], 20);
      expect(route('aadha ghanta baad jaga dena').args['minute'], 30);
    });
    test('clock-time alarms still work', () {
      expect((route('alarm 6:30 pe lagao', now: night).args['hour'], route('alarm 6:30 pe lagao', now: night).args['minute']), (6, 30));
      expect(route('set an alarm for 7 am').args['hour'], 7);
      expect(route('shaam 7 baje ka alarm').args['hour'], 19);
    });
    test('"kal 8 baje" said at 7 am would ring today — so it asks first', () {
      final p = route('kal subah 8 baje ka alarm laga do');
      expect(p.tool, 'alarm');
      expect(p.needsApproval, isTrue);
      expect(p.args['tomorrowClash'], isTrue);
    });
    test('"kal 8 baje" said at night is fine', () {
      final p = route('kal subah 8 baje ka alarm laga do', now: night);
      expect(p.needsApproval, isFalse);
      expect(p.args['hour'], 8);
    });
    test('cancel instead of asking what time', () {
      expect(route('alarm band karo').tool, 'cancel_alarm');
      expect(route('alarm cancel karo').args, isEmpty);
      final p = route('6 baje wala alarm hata do', now: night);
      expect(p.tool, 'cancel_alarm');
      expect(p.args['hour'], 6);
    });
    test('asking which alarm is set', () {
      expect(route('alarm kitne baje ka hai').tool, 'next_alarm');
      expect(route('mera next alarm kab hai').tool, 'next_alarm');
      expect(route('kal ka alarm laga do 6 baje').tool, 'alarm');
    });
    test('timers can be stopped too', () {
      expect(route('timer band karo').tool, 'cancel_timer');
      expect(route('cancel the timer').tool, 'cancel_timer');
      expect(route('10 minute ka timer lagao').tool, 'timer');
    });
  });

  group('reminders', () {
    test('at a time: an alarm labelled with the reminder', () {
      final p = route('kal 9 baje yaad dilana ki dawai leni hai', now: night);
      expect(p.tool, 'remind');
      expect((p.args['hour'], p.args['minute']), (9, 0));
      expect(p.args['text'], 'dawai leni hai');
    });
    test('English', () {
      final p = route('remind me to call mom at 5');
      expect(p.tool, 'remind');
      expect(p.args['hour'], 17);
      expect(p.args['text'], 'call mom');
    });
    test('relative: a labelled timer', () {
      final p = route('10 minute baad yaad dilana ki chai bana li');
      expect(p.tool, 'remind');
      expect(p.args['seconds'], 600);
      expect(p.args['text'], 'chai bana li');
      expect(route('20 minute baad batana').args['seconds'], 1200);
    });
    test('the "when" is cut out of the text, even when it comes first', () {
      expect(route('kal subah 9 baje dawai lene ka yaad dilana', now: night).args['text'], 'dawai lene');
      expect(route('remember to buy milk at 6').args['text'], 'buy milk');
    });
    test('no time → asks when, keeping what', () {
      final p = route('yaad dilana ki ravi ka birthday hai');
      expect(p.tool, 'clarify');
      expect(p.args['for'], 'remind');
      expect(p.args['text'], 'ravi ka birthday hai');
    });
    test('"remember …" without a time is still a note', () {
      expect(route('remember that the wifi password is tiger123').tool, 'remember');
      expect(route('yaad rakho ki car B2 mein hai').tool, 'remember');
    });
  });

  group('the phone is not a person', () {
    test('ringer', () {
      expect(route('phone silent karo').args, {'mode': 'silent'});
      expect(route('phone silent pe daal do').tool, 'ringer');
      expect(route('silent mode hatao').args, {'mode': 'normal'});
      expect(route('phone vibrate pe karo').args, {'mode': 'vibrate'});
      expect(route('dnd on karo').args, {'mode': 'silent'});
    });
    test('"ring tone change karo" and "phone restart karo" never call anyone', () {
      expect(route('ring tone change karo').tool, isNot('call'));
      expect(route('phone restart karo').tool, isNot('call'));
    });
    test('real calls still work', () {
      expect(route('call mummy').args['to'], 'mummy');
      expect(route('phone papa').args['to'], 'papa');
      expect(route('Ravi ko call karo').args['to'], 'ravi');
    });
  });

  group('torch needs a switch word', () {
    test('shopping and searching are not torch commands', () {
      expect(route('flipkart flash sale search karo').tool, 'search');
      expect(route('torch kharidna hai').tool, isNot('torch'));
    });
    test('torch commands', () {
      expect(route('torch on karo').args, {'on': true});
      expect(route('flash on karo').args, {'on': true});
      expect(route('torch').args, {'on': true});
      expect(route('flashlight band karo').args, {'on': false});
    });
  });

  group('volume and music', () {
    test('volume', () {
      expect(route('volume badhao').args, {'action': 'up'});
      expect(route('awaaz kam karo').args, {'action': 'down'});
      expect(route('volume full kar do').args, {'action': 'max'});
      expect(route('volume 50 pe karo').args, {'action': 'set', 'level': 50});
      expect(route('sound mute karo').args, {'action': 'mute'});
    });
    test('what is playing', () {
      expect(route('gaana band karo').args, {'action': 'pause'});
      expect(route('next song').args, {'action': 'next'});
      expect(route('agla gaana').args, {'action': 'next'});
      expect(route('pichla gaana lagao').args, {'action': 'previous'});
      expect(route('pause').args, {'action': 'pause'});
    });
    test('play something', () {
      expect(route('gaana bajao').args, {'q': ''});
      expect(route('play arijit singh songs').args, {'q': 'arijit singh songs'});
      expect(route('arijit singh ke gaane bajao').args, {'q': 'arijit singh ke gaane'});
      expect(route('play believer on spotify').args, {'q': 'believer', 'app': 'spotify'});
      expect(route('youtube pe kesariya bajao').args, {'q': 'kesariya', 'app': 'youtube'});
      expect(route('music chalu karo').tool, 'play');
      expect(route('start music').tool, 'play');
    });
    test('neighbours stay put', () {
      expect(route('play store kholo').tool, 'open');
      expect(route('joke sunao').tool, isNot('play'));
      expect(route('alarm laga do 6 baje').tool, 'alarm');
    });
  });

  group('quick settings, maps, live info', () {
    test('settings Android won\'t flip open their panel', () {
      expect(route('wifi on karo').args, {'which': 'wifi', 'on': true});
      expect(route('bluetooth band karo').args, {'which': 'bluetooth', 'on': false});
      expect(route('mobile data on karo').args['which'], 'mobile_data');
      expect(route('location chalu karo').args['which'], 'location');
      expect(route('wifi kholo').tool, 'open'); // the settings page, as before
    });
    test('directions', () {
      expect(route('ghar ka rasta dikhao').args, {'place': 'Home'});
      expect(route('office kaise jaun').args, {'place': 'Work'});
      expect(route('navigate to india gate').args, {'place': 'india gate'});
      expect(route('connaught place le chalo').args, {'place': 'connaught place'});
    });
    test('live info asks before going online', () {
      for (final s in ['aaj mausam kaisa hai', 'what time is the match', 'train ka time kya hai', 'aaj ki news batao']) {
        final p = route(s);
        expect((p.tool, p.args['reason'], p.needsApproval), ('search', 'live_info', true), reason: s);
      }
    });
    test('the clock is still the clock', () {
      expect(route('time kya hua').tool, 'time');
      expect(route('what time is it').tool, 'time');
      expect(route('abhi ka time batao').tool, 'time');
    });
  });

  group('messages', () {
    test('"papa ko bolo ki …" sends a message', () {
      final p = route('papa ko bolo ki main late aaunga');
      expect((p.tool, p.args['to'], p.args['body'], p.needsApproval), ('message', 'papa', 'main late aaunga', true));
    });
    test('"message bhejo papa ko" asks what to say', () {
      final p = route('ek message bhejo papa ko');
      expect((p.tool, p.args['for'], p.args['to']), ('clarify', 'message', 'papa'));
    });
    test('a message\'s text never runs as a command', () {
      expect(route('Ravi ko message karo ki volume kam kar de').tool, 'message');
      expect(route('Ravi ko whatsapp karo ki torch le aana').tool, 'message');
    });
    test('a reminder about messaging is not a message to "yaad dilana ki ravi"', () {
      final p = route('yaad dilana ki ravi ko message karo');
      expect((p.tool, p.args['for'], p.args['text']), ('clarify', 'remind', 'ravi ko message karo'));
    });
    test('"mujhe batao" is not a message to "mujhe"', () {
      expect(route('mujhe batao ki time kya hai').tool, isNot('message'));
    });
  });

  test('"help" only for help with AERIS itself', () {
    expect(route('mujhe help chahiye bank account kholne mein').tool, isNot('help'));
    expect(route('help').tool, 'help');
    expect(route('tum kya kar sakte ho').tool, 'help');
  });

  test('reminderText strips the time words', () {
    expect(Router.reminderText(normalize('kal subah 9 baje yaad dilana ki dawai leni hai')), 'dawai leni hai');
  });
}
