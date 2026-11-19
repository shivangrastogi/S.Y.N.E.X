// Phase 10 — the phone agent's loop, driven end-to-end with a fake phone and
// a scripted brain: no device, no network. The fake records every call, so
// these tests prove what AERIS *does* (and refuses to do), not just what it
// says.
import 'package:flutter_test/flutter_test.dart';
import 'package:aeris_remote/core/lang.dart';
import 'package:aeris_remote/assistant/phone_agent.dart';

class FakePhone implements AgentDevice {
  final List<String> screens; // returned in order; the last one repeats
  int _screen = 0;
  final calls = <String>[];
  String imageError = '';

  FakePhone(this.screens);

  @override
  Future<String> screen() async =>
      screens[_screen < screens.length ? _screen++ : screens.length - 1];
  @override
  Future<bool> tap(int id) async => _log('tap $id');
  @override
  Future<bool> longPress(int id) async => _log('long_press $id');
  @override
  Future<bool> type(int id, String text) async => _log('type $id "$text"');
  @override
  Future<bool> enter() async => _log('enter');
  @override
  Future<bool> scroll(bool forward) async => _log('scroll $forward');
  @override
  Future<bool> global(String which) async => _log(which);
  @override
  Future<bool> openApp(String name) async =>
      _log('open $name') && name != 'Missing';
  @override
  Future<List<String>> apps() async => ['ChatGPT', 'Gemini', 'WhatsApp'];
  @override
  Future<List<(String, String)>> contacts(String name) async =>
      name.toLowerCase() == 'ravi' ? [('Ravi Kumar', '919876543210')] : [];
  @override
  Future<String> whatsappLatestImage(String phone) async {
    _log('wa_image $phone');
    return imageError;
  }

  @override
  Future<bool> whatsappChat(String phone, String text) async =>
      _log('wa_chat $phone "$text"');
  @override
  Future<String?> skill(String command) async {
    _log('skill $command');
    return command.contains('torch') ? 'Torch on kar di.' : null;
  }

  @override
  Future<void> wait(Duration d) async {}

  bool _log(String c) {
    calls.add(c);
    return true;
  }
}

/// Replays [replies] in order and records every prompt it was shown.
class ScriptedBrain {
  final List<Object> replies; // Map, or an Exception to throw
  final prompts = <String>[];
  int _i = 0;
  ScriptedBrain(this.replies);

  Future<Map<String, dynamic>> call(String system, String prompt) async {
    prompts.add(prompt);
    final r = replies[_i < replies.length ? _i++ : replies.length - 1];
    if (r is Exception) throw r;
    return r as Map<String, dynamic>;
  }
}

const sendsPlan = AgentPlan(true, 'Image banwa ke Ravi ko bhejunga.',
    ['Gemini mein image banao', 'Ravi ko WhatsApp pe bhejo'], true, 'Ravi');
const quietPlan =
    AgentPlan(true, 'Torch jala raha hoon.', ['Torch on karo'], false, '');

const geminiHome = 'app: com.google.android.apps.bard\n'
    '[0] EditText "Ask Gemini" type\n'
    '[1] Button "Send message" tap';
const geminiImage = 'app: com.google.android.apps.bard\n'
    '[0] ImageView "Generated image" tap,long_press\n'
    '[1] Button "Download" tap\n'
    '[2] Button "Share" tap';
const waPreview = 'app: com.whatsapp\n'
    '[0] EditText "Add a caption" type\n'
    '[1] ImageButton "Send" tap';

PhoneAgent agent(FakePhone p, ScriptedBrain b, {int maxSteps = 30}) =>
    PhoneAgent(
        device: p, brain: b.call, maxSteps: maxSteps, settle: Duration.zero);

void main() {
  group('looksLikeTask', () {
    const tasks = [
      'Hi Jarvis firstly generate image of a person standing in kitchen '
          'and send to my Ravi on whatsapp',
      'ek sunset ki photo banao',
      'kitchen mein khade aadmi ki image bana ke ravi ko bhejo',
      'youtube kholo phir lofi music search karo',
      'pehle whatsapp kholo uske baad mummy ko photo bhejo',
      'ye kaam khud karo',
    ];
    const notTasks = [
      'torch on karo',
      'mummy ko whatsapp pe hello bolo',
      'phir se bolo',
      'aaj ka weather kya hai',
      'rahul ko call karo',
      'what is the first law of motion',
      'photo dikhao',
    ];
    for (final t in tasks) {
      test('task: "$t"', () => expect(PhoneAgent.looksLikeTask(t), isTrue));
    }
    for (final t in notTasks) {
      test('not a task: "$t"',
          () => expect(PhoneAgent.looksLikeTask(t), isFalse));
    }
  });

  test('isYes: a yes word and no no word', () {
    for (final y in ['haan', 'haan bhejo', 'ok kar do', 'yes', 'theek hai']) {
      expect(PhoneAgent.isYes(y), isTrue, reason: y);
    }
    for (final n in ['nahi', 'ok mat karo', 'cancel', 'rehne do', 'kuch aur']) {
      expect(PhoneAgent.isYes(n), isFalse, reason: n);
    }
  });

  test('screen parsing: element label + foreground app', () {
    expect(PhoneAgent.labelFor(geminiImage, 1), 'Download');
    expect(PhoneAgent.labelFor(geminiImage, 9), '');
    expect(PhoneAgent.appOf(waPreview), 'com.whatsapp');
  });

  test('plan: shows the planner the installed apps and parses its JSON',
      () async {
    final b = ScriptedBrain([
      {
        'is_task': true,
        'summary': 'Gemini se image banwa ke Ravi ko bhejunga.',
        'steps': ['Gemini kholo', 'WhatsApp pe bhejo'],
        'messages_someone': true,
        'recipient': 'Ravi',
      }
    ]);
    final plan = await agent(FakePhone([geminiHome]), b).plan('image bhejo');
    expect(b.prompts.single, contains('Gemini'));
    expect(plan!.isTask, isTrue);
    expect(plan.messagesSomeone, isTrue);
    expect(plan.steps, hasLength(2));
  });

  test('plan: brain unreachable → null (caller falls through)', () async {
    final b = ScriptedBrain([Exception('offline')]);
    expect(await agent(FakePhone([geminiHome]), b).plan('x'), isNull);
  });

  test('the full example: Gemini image → WhatsApp → Ravi', () async {
    final phone = FakePhone([
      'app: com.aeris.aeris_remote\n[0] TextView "AERIS"',
      geminiHome,
      geminiHome,
      geminiHome,
      geminiImage,
      geminiImage,
      waPreview,
      'app: com.whatsapp\n[0] TextView "Ravi Kumar"\n[1] ImageView "Photo"',
    ]);
    final b = ScriptedBrain([
      {'action': 'open_app', 'app': 'Gemini'},
      {
        'action': 'type',
        'id': 0,
        'text': 'Generate an image of a person standing in a kitchen'
      },
      {'action': 'tap', 'id': 1},
      {'action': 'wait', 'seconds': 10},
      {'action': 'tap', 'id': 1}, // Download
      {'action': 'whatsapp_send_latest_image', 'contact': 'Ravi'},
      {'action': 'tap', 'id': 1}, // Send
      {'action': 'done', 'summary': 'Ravi ko image bhej di.'},
    ]);
    final progress = <String>[];
    final res = await agent(phone, b).run('image bhejo', sendsPlan,
        onProgress: progress.add);
    expect(res.ok, isTrue);
    expect(res.summary, 'Ravi ko image bhej di.');
    expect(phone.calls, [
      'open Gemini',
      'type 0 "Generate an image of a person standing in a kitchen"',
      'tap 1',
      'tap 1',
      'wa_image 919876543210',
      'tap 1',
    ]);
    // Each step sees what happened before it.
    expect(b.prompts.last, contains('whatsapp_send_latest_image Ravi'));
    expect(b.prompts.last, contains('now tap Send'));
  });

  test('unapproved plan: a Send tap inside WhatsApp is blocked', () async {
    final phone = FakePhone([waPreview]);
    final b = ScriptedBrain([
      {'action': 'tap', 'id': 1},
      {'action': 'fail', 'reason': 'Bhejne ki permission nahi thi.'},
    ]);
    final res = await agent(phone, b).run('x', quietPlan);
    expect(res.ok, isFalse);
    expect(phone.calls, isEmpty);
    expect(b.prompts.last, contains('BLOCKED'));
  });

  test('unapproved plan: WhatsApp tools are blocked too', () async {
    final phone = FakePhone([geminiImage]);
    final b = ScriptedBrain([
      {'action': 'whatsapp_send_latest_image', 'contact': 'Ravi'},
      {'action': 'whatsapp_chat', 'contact': 'Ravi', 'text': 'hi'},
      {'action': 'done'},
    ]);
    await agent(phone, b).run('x', quietPlan);
    expect(phone.calls, isEmpty);
  });

  test('payment / upgrade buttons are never tapped, even when approved',
      () async {
    final phone = FakePhone(['app: com.google.android.apps.bard\n'
        '[0] Button "Upgrade to Gemini Advanced" tap']);
    final b = ScriptedBrain([
      {'action': 'tap', 'id': 0},
      {'action': 'done'},
    ]);
    await agent(phone, b).run('x', sendsPlan);
    expect(phone.calls, isEmpty);
    expect(b.prompts.last, contains('BLOCKED'));
  });

  test('a Send tap outside messaging apps is fine (Gemini prompt)', () async {
    final phone = FakePhone([geminiHome]);
    final b = ScriptedBrain([
      {'action': 'tap', 'id': 1},
      {'action': 'done'},
    ]);
    await agent(phone, b).run('x', quietPlan);
    expect(phone.calls, ['tap 1']);
  });

  test('built-in phone skills are tools', () async {
    final phone = FakePhone([geminiHome]);
    final b = ScriptedBrain([
      {'action': 'skill', 'command': 'torch on karo'},
      {'action': 'done', 'summary': 'Torch on.'},
    ]);
    final res = await agent(phone, b).run('x', quietPlan);
    expect(res.ok, isTrue);
    expect(b.prompts.last, contains('Torch on kar di.'));
  });

  test('a failed attachment is reported back to the brain', () async {
    final phone = FakePhone([geminiImage])
      ..imageError = 'no image saved in the last 15 minutes';
    final b = ScriptedBrain([
      {'action': 'whatsapp_send_latest_image', 'contact': 'Ravi'},
      {'action': 'fail', 'reason': 'Image save nahi hui.'},
    ]);
    await agent(phone, b).run('x', sendsPlan);
    expect(b.prompts.last, contains('FAILED: no image saved'));
  });

  test('unknown contact is reported, WhatsApp never opened', () async {
    final phone = FakePhone([geminiImage]);
    final b = ScriptedBrain([
      {'action': 'whatsapp_send_latest_image', 'contact': 'Nobody'},
      {'action': 'fail', 'reason': 'Contact nahi mila.'},
    ]);
    await agent(phone, b).run('x', sendsPlan);
    expect(phone.calls, isEmpty);
    expect(b.prompts.last, contains('contact not found'));
  });

  test('repeating the same action on the same screen earns a nudge',
      () async {
    final phone = FakePhone([geminiHome]);
    final b = ScriptedBrain([
      {'action': 'tap', 'id': 0},
      {'action': 'tap', 'id': 0},
      {'action': 'tap', 'id': 0},
      {'action': 'fail', 'reason': 'Atak gaya.'},
    ]);
    await agent(phone, b).run('x', quietPlan);
    expect(b.prompts.last, contains('do something different'));
  });

  test('step cap stops a runaway loop', () async {
    final phone = FakePhone([geminiHome]);
    final b = ScriptedBrain([
      {'action': 'scroll', 'direction': 'down'}
    ]);
    final res = await agent(phone, b, maxSteps: 5).run('x', quietPlan);
    expect(res.ok, isFalse);
    expect(phone.calls, hasLength(5));
  });

  test('cancel stops before the next step', () async {
    final phone = FakePhone([geminiHome]);
    final b = ScriptedBrain([
      {'action': 'scroll'}
    ]);
    var steps = 0;
    final res = await agent(phone, b)
        .run('x', quietPlan, onProgress: (_) {}, cancelled: () => ++steps > 2);
    expect(res.ok, isFalse);
    expect(res.summary, contains('rok diya'));
    expect(phone.calls, hasLength(2));
  });

  test('three brain errors in a row → gives up cleanly', () async {
    final phone = FakePhone([geminiHome]);
    final b = ScriptedBrain([Exception('429')]);
    final res = await agent(phone, b).run('x', quietPlan);
    expect(res.ok, isFalse);
    expect(b.prompts, hasLength(3));
    expect(phone.calls, isEmpty);
  });

  group('English mode', () {
    tearDown(() => Lang.mode.value = LangMode.hinglish);

    test('prompts ask for English and canned replies are English', () async {
      Lang.mode.value = LangMode.englishIn;
      final b = ScriptedBrain([
        {'action': 'scroll'}
      ]);
      final systems = <String>[];
      final res = await PhoneAgent(
          device: FakePhone([geminiHome]),
          brain: (sys, p) {
            systems.add(sys);
            return b.call(sys, p);
          },
          settle: Duration.zero).run('x', quietPlan, cancelled: () => true);
      expect(res.summary, 'Okay, I stopped.');
      final plan = await PhoneAgent(
          device: FakePhone([geminiHome]),
          brain: (sys, p) async {
            systems.add(sys);
            return {'is_task': false};
          }).plan('x');
      expect(plan!.isTask, isFalse);
      expect(systems.last, contains('simple English'));
      expect(systems.last, isNot(contains('{LANG}')));
    });

    test('English yes/no', () {
      expect(PhoneAgent.isYes('yes go ahead'), isTrue);
      expect(PhoneAgent.isYes('sure, send it'), isTrue);
      expect(PhoneAgent.isYes("no don't"), isFalse);
      expect(PhoneAgent.isYes('nope'), isFalse);
    });
  });
}
