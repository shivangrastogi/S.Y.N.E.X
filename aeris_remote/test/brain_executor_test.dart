// The brain's tool calls → phone effects, on a fake device; plus the
// decide() loop on a scripted runtime and the spoken-math evaluator.
import 'dart:io';

import 'package:aeris_remote/brain/brain.dart';
import 'package:aeris_remote/brain/calc.dart';
import 'package:aeris_remote/brain/executor.dart';
import 'package:aeris_remote/brain/memory_store.dart';
import 'package:aeris_remote/brain/runtime.dart';
import 'package:aeris_remote/core/lang.dart';
import 'package:aeris_remote/assistant/phone_skills.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeActions implements BrainActions {
  final log = <String>[];
  double vol = 0.5;
  bool a11y = true;
  Map<String, List<(String, String)>> book = {
    'ravi': [('Ravi Kumar', '919876543210')],
  };
  @override
  final MemoryStore memory;
  FakeActions(this.memory);

  @override
  Future<void> torch(bool on) async => log.add('torch:$on');
  @override
  Future<double> getVolume() async => vol;
  @override
  Future<void> setVolume(double v) async {
    vol = v;
    log.add('volume:${(v * 100).round()}');
  }

  @override
  Future<bool> intent(String action,
      {String? data, Map<String, dynamic>? args, String? package, String? category}) async {
    log.add('intent:$action${data == null ? '' : ' $data'}${args == null ? '' : ' $args'}');
    return true;
  }

  @override
  Future<bool> openUrl(String url) async {
    log.add('url:$url');
    return true;
  }

  @override
  Future<List<(String, String)>> contacts(String name) async => book[name.toLowerCase()] ?? const [];
  @override
  Future<bool> openApp(String name) async {
    log.add('app:$name');
    return true;
  }

  @override
  Future<PhoneSkillResult?> legacy(String phrase) async {
    log.add('legacy:$phrase');
    return PhoneSkillResult('legacy ok');
  }

  @override
  Future<bool> a11yEnabled() async => a11y;
  @override
  Future<bool> global(String action) async {
    log.add('global:$action');
    return true;
  }

  @override
  Future<bool> scroll(bool forward) async => true;
  @override
  Future<bool> tap(String target) async => true;
  @override
  Future<void> media(String key) async => log.add('media:$key');
  @override
  Future<String?> cloud(String prompt) async => null;
  @override
  Future<void> setLanguage(LangMode m) async => log.add('lang:${m.name}');
  @override
  DateTime now() => DateTime(2026, 10, 18, 9, 0);
}

class ScriptedRuntime implements BrainRuntime {
  ScriptedRuntime(this.outputs);
  final List<String> outputs;
  final prompts = <String>[];
  String? lastGrammar;
  bool loaded = false;
  @override
  bool get isLoaded => loaded;
  @override
  Future<void> load(String modelPath, {int threads = 4, int contextSize = 4096}) async => loaded = true;
  @override
  Future<bool> warmPrefix(String prefix, String cacheFile) async => false;
  @override
  Future<BrainGeneration> complete(String prompt,
      {String? grammar, int maxTokens = 256, List<String> stop = const []}) async {
    prompts.add(prompt);
    lastGrammar = grammar;
    return BrainGeneration(outputs.removeAt(0), 10, 5, 20);
  }

  @override
  void cancel() {}
  @override
  Future<void> unload() async => loaded = false;
}

void main() {
  late Directory tmp;
  late FakeActions fx;
  late BrainExecutor ex;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('brain');
    fx = FakeActions(MemoryStore(file: File('${tmp.path}/mem.json')));
    ex = BrainExecutor(fx);
    Lang.mode.value = LangMode.englishIn;
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  test('flashlight + volume set in one turn', () async {
    final r = await ex.runAll([
      {'name': 'flashlight', 'args': {'state': 'on'}},
      {'name': 'volume', 'args': {'action': 'set', 'level': 40}},
    ]);
    expect(fx.log, ['torch:true', 'volume:40']);
    expect(r.spoken, 'Flashlight on. Volume at 40 percent.');
  });

  test('alarm span "shaam 6 baje" → 18:00 with label', () async {
    final r = await ex.run('set_alarm', {'time': 'shaam 6 baje', 'label': 'gym'});
    expect(fx.log.single, contains('HOUR: 18'));
    expect(fx.log.single, contains('MESSAGE: gym'));
    expect(r.spoken, 'Alarm set for 18:00.');
  });

  test('timer spans incl. spoken amounts', () async {
    await ex.run('set_timer', {'duration': 'aadha ghanta'});
    await ex.run('set_timer', {'duration': 'ten minutes'});
    await ex.run('set_timer', {'duration': '1 hour 5 minute'});
    expect(fx.log[0], contains('LENGTH: 1800'));
    expect(fx.log[1], contains('LENGTH: 600'));
    expect(fx.log[2], contains('LENGTH: 3900'));
  });

  test('message: contact resolved, prefilled WhatsApp, never auto-sent', () async {
    final r = await ex.run('send_message', {'contact': 'Ravi', 'message': 'main 10 minute mein aa raha hoon'});
    expect(fx.log.single, startsWith('url:https://wa.me/919876543210?text=main%2010'));
    expect(r.spoken, contains('Tap send'));
  });

  test('message to unknown contact fails without acting', () async {
    final r = await ex.run('send_message', {'contact': 'Mohan', 'message': 'hi'});
    expect(r.outcome, BrainOutcome.failed);
    expect(fx.log, isEmpty);
  });

  test('spoken number wins over contacts; SMS when asked', () async {
    await ex.run('send_message', {'number': '7300 978845', 'message': 'hi', 'app': 'sms'});
    expect(fx.log.single, 'url:smsto:7300978845?body=hi');
  });

  test('call by phone vs WhatsApp video', () async {
    await ex.run('call', {'contact': 'ravi'});
    await ex.run('call', {'contact': 'ravi', 'video': true});
    expect(fx.log[0], 'intent:android.intent.action.CALL tel:919876543210');
    expect(fx.log[1], 'url:https://wa.me/919876543210');
  });

  test('screen tools refuse politely when screen control is off', () async {
    fx.a11y = false;
    final r = await ex.run('navigate_phone', {'action': 'back'});
    expect(r.outcome, BrainOutcome.failed);
    expect(fx.log, isEmpty);
  });

  test('remember → recall → forget round trip', () async {
    await ex.run('remember', {'fact': 'my locker code is 4412'});
    await ex.run('remember', {'fact': 'Ravi is my brother'});
    expect((await ex.run('recall', {'query': 'locker code'})).spoken, contains('4412'));
    expect((await ex.run('forget', {'query': 'locker'})).spoken, contains('Forgotten'));
    expect((await ex.run('recall', {'query': 'locker code'})).spoken, contains("don't have"));
  });

  test('navigation, email, reminder, language, hand-offs', () async {
    await ex.run('navigate_to', {'destination': 'India Gate', 'mode': 'walking'});
    expect(fx.log.last, 'url:google.navigation:q=India%20Gate&mode=w');
    await ex.run('send_email', {'to': 'a@b.com', 'subject': 'Hi'});
    expect(fx.log.last, 'url:mailto:a@b.com?subject=Hi');
    await ex.run('set_reminder', {'text': 'call mom', 'when': '5 pm'});
    expect(fx.log.last, contains('MESSAGE: call mom'));
    await ex.run('set_language', {'mode': 'english_us'});
    expect(fx.log.last, 'lang:englishUs');
    final lap = await ex.run('laptop_command', {'command': 'open chrome'});
    expect((lap.outcome, lap.payload), (BrainOutcome.laptop, 'open chrome'));
    expect((await ex.run('end_conversation', {'mode': 'sleep'})).outcome, BrainOutcome.endSleep);
  });

  test('calendar event tomorrow gets the right epoch', () async {
    await ex.run('create_calendar_event', {'title': 'Dentist', 'when': 'kal 11 baje'});
    final begin = DateTime(2026, 10, 19, 11).millisecondsSinceEpoch;
    expect(fx.log.last, contains('beginTime: $begin'));
  });

  group('calculate', () {
    for (final (expr, want) in [
      ('25 into 4', 100.0),
      ('15 percent of 200', 30.0),
      ('100 divided by 8 plus 3', 15.5),
      ('(2+3)*4', 20.0),
      ('50 ka 20 percent', 10.0),
      ('2 + 3 * 4', 14.0),
      ('-5 plus 2', -3.0),
    ]) {
      test(expr, () => expect(calculate(expr), want));
    }
    test('non-math is null', () {
      expect(calculate('call ravi'), isNull);
      expect(calculate('42'), isNull);
    });
    test('pretty', () {
      expect(prettyNumber(15.5), '15.5');
      expect(prettyNumber(100), '100');
      expect(prettyNumber(1 / 3), '0.33');
    });
  });

  group('AerisBrain.decide (scripted runtime)', () {
    final toolsJson = File('assets/brain/tools.json').readAsStringSync();

    test('valid, grounded tool call', () async {
      final rt = ScriptedRuntime(['{"type":"tool_call","calls":[{"name":"call","args":{"contact":"Ravi"}}]}']);
      final b = AerisBrain(runtime: rt, toolsJson: toolsJson, supportDir: tmp.path);
      await b.setModelPath(File('assets/brain/tools.json').absolute.path); // any existing file
      final d = (await b.decide('Ravi ko call karo', commit: false))!;
      expect(d.valid, isTrue, reason: d.errors.join());
      expect(d.summary, 'call({"contact":"Ravi"})');
      expect(rt.prompts.single, endsWith('<|im_start|>user\nRavi ko call karo<|im_end|>\n'
          '<|im_start|>assistant\n<think>\n\n</think>\n\n'));
      expect(rt.lastGrammar, startsWith('root ::= '));
    });

    test('hallucinated contact is rejected (grounding)', () async {
      final rt = ScriptedRuntime(['{"type":"tool_call","calls":[{"name":"call","args":{"contact":"Mohan"}}]}']);
      final b = AerisBrain(runtime: rt, toolsJson: toolsJson, supportDir: tmp.path);
      await b.setModelPath(File('assets/brain/tools.json').absolute.path);
      final d = (await b.decide('Ravi ko call karo', commit: false))!;
      expect(d.valid, isFalse);
    });

    test('ask → answer keeps context for the follow-up', () async {
      final rt = ScriptedRuntime([
        '{"type":"ask","text":"What should I tell Ravi?","pending":"send_message"}',
        '{"type":"tool_call","calls":[{"name":"send_message","args":{"contact":"Ravi","message":"running late"}}]}',
      ]);
      final b = AerisBrain(runtime: rt, toolsJson: toolsJson, supportDir: tmp.path);
      await b.setModelPath(File('assets/brain/tools.json').absolute.path);
      expect((await b.decide('message Ravi'))!.type, 'ask');
      final d2 = (await b.decide('running late'))!;
      expect(d2.valid, isTrue, reason: d2.errors.join()); // "Ravi" grounded by turn 1
      expect(rt.prompts.last, contains('<|im_start|>assistant\n{"type":"ask"'));
    });
  });
}
