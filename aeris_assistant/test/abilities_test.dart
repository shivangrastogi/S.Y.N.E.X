import 'dart:convert';

import 'package:aeris_assistant/brain/executor.dart';
import 'package:aeris_assistant/brain/llm/bridge.dart';
import 'package:aeris_assistant/brain/phone.dart';
import 'package:aeris_assistant/brain/router.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:aeris_assistant/voice/session.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fakes.dart';

/// The 2026-11-17 review: new abilities and the fixes behind them, end to end
/// through the executor and the voice session (fake phone, fake ears/mouth).
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(SystemChannels.platform, (_) async => null);

  late Store store;
  late FakePhone phone;
  late FakeMouth mouth;

  VoiceSession make(List<String?> script, {List<Person>? people}) {
    store = Store.memory()..settings = const Settings(onboarded: true);
    phone = FakePhone();
    if (people != null) phone.people = people;
    mouth = FakeMouth();
    return VoiceSession(store: store, ears: FakeEars(script), mouth: mouth, exec: Executor(phone, store));
  }

  Future<void> settle() async {
    for (var i = 0; i < 30; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  Future<Outcome> run(String said, {DateTime? now}) async {
    store = Store.memory()..settings = const Settings(onboarded: true);
    phone = FakePhone();
    final plan = const Router().route(said, now: now ?? DateTime(2026, 11, 17, 22, 0));
    return Executor(phone, store).run(plan);
  }

  group('approval', () {
    test('a new command while a message waits does NOT send it', () async {
      final s = make(['Ravi ko WhatsApp karo ki main late hoon', 'Mummy ko call karo']);
      await s.start();
      await settle();
      expect(phone.calls, isNot(contains(startsWith('wa '))));
      expect(phone.calls, contains('dial 99999 00000'));
    });

    test('"haan bhej do na" sends it', () async {
      final s = make(['Ravi ko WhatsApp karo ki main late hoon', 'haan bhej do na']);
      await s.start();
      await settle();
      expect(phone.calls, ['wa 98765 43210 main late hoon']);
    });
  });

  group('which Rahul?', () {
    final twoRahuls = [const Person('Rahul Sharma', '90000 11111'), const Person('Rahul Office', '90000 22222')];

    test('two equal matches → asks, then dials the one named', () async {
      final s = make(['Rahul ko call karo', 'office wala'], people: twoRahuls);
      await s.start();
      await settle();
      expect(mouth.said.first, 'Kaunse Rahul? Rahul Sharma ya Rahul Office?');
      expect(phone.calls, ['dial 90000 22222']);
    });

    test('"pehla" picks the first', () async {
      final s = make(['call rahul', 'pehla'], people: twoRahuls);
      await s.start();
      await settle();
      expect(phone.calls, ['dial 90000 11111']);
    });

    test('messages ask too, before the approval', () async {
      final s = make(['Rahul ko message karo ki 5 baje milte hain', 'sharma', 'haan'], people: twoRahuls);
      await s.start();
      await settle();
      expect(phone.calls, ['sms 90000 11111 5 baje milte hain']);
    });

    test('one clear match never asks', () async {
      final s = make(['Rahul Sharma ko call karo'], people: twoRahuls);
      await s.start();
      await settle();
      expect(phone.calls, ['dial 90000 11111']);
    });
  });

  group('contacts', () {
    test('family words find how the contact is saved', () {
      final people = [const Person('Maa', '1'), const Person('Papa Ji', '2'), const Person('Rohan Bhaiya', '3')];
      expect(rankPeople(people, 'mummy').first.name, 'Maa');
      expect(rankPeople(people, 'dad').first.name, 'Papa Ji');
      expect(rankPeople(people, 'papa').first.name, 'Papa Ji');
    });
    test('contacts saved in Hindi script match', () {
      final people = [const Person('पापा', '1'), const Person('Ravi', '2')];
      expect(rankPeople(people, 'papa').first.number, '1');
    });
    test('"mama" is an uncle, never mummy', () {
      expect(rankPeople([const Person('Mama Ji', '1')], 'mummy'), isEmpty);
    });
    test('the same number saved twice is one person', () {
      expect(topMatches([const Person('Ravi', '98765 43210'), const Person('Ravi', '+91 9876543210')], 'ravi').length, 2);
      expect(topMatches([const Person('Ravi', '98765 43210'), const Person('Ravi', '9876543210')], 'ravi').length, 1);
    });
  });

  group('new abilities', () {
    test('reminder at a time = labelled alarm', () async {
      final o = await run('kal 9 baje yaad dilana ki dawai leni hai');
      expect(phone.calls, ['alarm 9:0']);
      expect(o.reply, '9:00 a.m. pe yaad dilaunga: dawai leni hai.');
    });
    test('relative reminder = labelled timer', () async {
      final o = await run('10 minute baad yaad dilana ki chai');
      expect(phone.calls, ['timer 600']);
      expect(o.reply, '10 minute baad yaad dilaunga: chai.');
    });
    test('alarm "for 5 minutes" rings in 5 minutes', () async {
      await run('alarm for 5 minutes', now: DateTime(2026, 11, 17, 7, 0));
      expect(phone.calls, ['alarm 7:5']);
    });
    test('cancel an alarm by time, or show the list', () async {
      await run('6 baje wala alarm hata do');
      expect(phone.calls, ['dismiss alarm 6:0']);
      final o = await run('alarm band karo');
      expect(phone.calls, ['show alarms']);
      expect(o.reply, contains('Alarms khol diye'));
    });
    test('next alarm', () async {
      store = Store.memory()..settings = const Settings(onboarded: true);
      phone = FakePhone()..next = DateTime.now().add(const Duration(days: 1)).copyWith(hour: 6, minute: 30);
      final o = await Executor(phone, store).run(const Plan('next_alarm'));
      expect(o.reply, 'Agla alarm kal 6:30 a.m. ka hai.');
    });
    test('silent without Do Not Disturb access opens the setting and says why', () async {
      store = Store.memory()..settings = const Settings(onboarded: true);
      phone = FakePhone()..hasDndAccess = false;
      final o = await Executor(phone, store).run(const Plan('ringer', {'mode': 'silent'}));
      expect(phone.calls, ['ringer silent', 'open dnd access']);
      expect(o.status, TurnStatus.failed);
      expect(o.reply, contains('Do Not Disturb'));
    });
    test('volume reports the real level', () async {
      final o = await run('volume badhao');
      expect(o.reply, 'Volume badha diya — ab 53%.');
    });
    test('"gaana bajao" resumes if something was paused, else starts a music app', () async {
      await run('gaana bajao');
      expect(phone.calls, ['media play', 'play ""']);
    });
    test('play a song in the named app', () async {
      final o = await run('play believer on spotify');
      expect(phone.calls, ['play "believer" on spotify']);
      expect(o.reply, 'Believer chala raha hoon.');
    });
    test('wifi: honest about the one tap Android needs', () async {
      final o = await run('wifi on karo');
      expect(phone.calls, ['setting wifi']);
      expect(o.reply, 'Wi-Fi ki setting khol di — on karne ke liye bas ek tap kijiye.');
    });
    test('directions home', () async {
      final o = await run('ghar ka rasta dikhao');
      expect(phone.calls, ['navigate Home']);
      expect(o.reply, 'Ghar ka rasta khol raha hoon.');
    });
    test('apps outside the built-in list are found among installed apps', () async {
      final o = await run('angel one kholo');
      expect(phone.calls, ['open com.msf.angelone']);
      expect(o.reply, 'Angel One khol raha hoon.');
    });
  });

  group('robustness', () {
    test('a plugin error is never read aloud', () async {
      store = Store.memory()..settings = const Settings(onboarded: true);
      final o = await Executor(_ThrowingPhone(), store).run(const Plan('torch', {'on': true}));
      expect(o.reply, 'Maaf kijiye, ye abhi nahi ho paaya.');
      expect(o.reply, isNot(contains('Exception')));
    });

    test('one damaged entry does not wipe the other memories', () async {
      SharedPreferences.setMockInitialValues({
        'activity.v1': jsonEncode([
          {'broken': true},
        ]),
        'memory.v1': jsonEncode([
          {'id': '1', 'text': 'Car B2 mein hai', 'c': DateTime(2026).toIso8601String()},
          {'id': 2},
        ]),
      });
      final loaded = await Store.open();
      expect(loaded.memories.map((m) => m.text), ['Car B2 mein hai']);
    });

    test('an unreadable list is kept aside before anything overwrites it', () async {
      SharedPreferences.setMockInitialValues({'memory.v1': '{not json'});
      final loaded = await Store.open();
      expect(loaded.memories, isEmpty);
      expect((await SharedPreferences.getInstance()).getString('memory.v1.unreadable'), '{not json');
    });

    test('focus mode really goes quiet now', () async {
      final focus = Store.defaultProtocols().firstWhere((p) => p.id == 'p_focus');
      expect(const Router().route(focus.actions.last).args, {'mode': 'vibrate'});
    });
  });

  group('brain → new abilities', () {
    Map<String, dynamic> call(String name, Map<String, dynamic> args) => {
          'type': 'tool_call',
          'calls': [
            {'name': name, 'args': args}
          ],
        };
    Plan planFor(Map<String, dynamic> contract) => (actionFromContract(contract, now: DateTime(2026, 11, 17, 22)) as BrainRunsPlan).plan;

    test('volume, music, settings, maps, reminders', () {
      expect(planFor(call('volume', {'action': 'down'})).args, {'action': 'down'});
      expect(planFor(call('media_control', {'action': 'stop'})).args, {'action': 'pause'});
      expect(planFor(call('play_music', {'query': 'kesariya', 'app': 'spotify'})).args, {'q': 'kesariya', 'app': 'spotify'});
      expect(planFor(call('toggle_setting', {'setting': 'dnd', 'state': 'on'})).args, {'mode': 'silent'});
      expect(planFor(call('toggle_setting', {'setting': 'wifi', 'state': 'off'})).args, {'which': 'wifi', 'on': false});
      expect(planFor(call('navigate_to', {'destination': 'ghar'})).args, {'place': 'Home'});
      final reminder = planFor(call('set_reminder', {'text': 'dawai leni hai', 'when': 'kal 9 baje'}));
      expect((reminder.tool, reminder.args['hour'], reminder.args['text']), ('remind', 9, 'dawai leni hai'));
    });

    test('a message with no contact or no text asks instead of showing an empty panel', () {
      final noContact = planFor(call('send_message', {'message': 'main late hoon'}));
      expect((noContact.tool, noContact.args['for']), ('clarify', 'message_to'));
      final noText = planFor(call('send_message', {'contact': 'Ravi'}));
      expect((noText.tool, noText.args['for']), ('clarify', 'message'));
    });
  });
}

/// A phone where every plugin call throws, like a PlatformException would.
class _ThrowingPhone extends FakePhone {
  @override
  Future<bool> torch(bool on) => throw PlatformException(code: 'torch', message: 'camera in use');
}
