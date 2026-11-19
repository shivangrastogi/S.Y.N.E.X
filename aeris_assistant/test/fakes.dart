import 'dart:async';

import 'package:aeris_assistant/brain/llm/runtime.dart';
import 'package:aeris_assistant/brain/phone.dart';
import 'package:aeris_assistant/calls/call_bridge.dart';
import 'package:aeris_assistant/calls/call_voice_rules.dart';
import 'package:aeris_assistant/voice/io.dart';

/// Ears the test drives: each listen() pops the next scripted utterance.
/// `null` in the script = silence.
class FakeEars implements Ears {
  FakeEars(this.script);
  final List<String?> script;
  int listens = 0;

  @override
  bool get available => true;
  @override
  Future<bool> init() async => true;

  @override
  Future<void> listen({
    required String locale,
    required void Function(String partial) onPartial,
    required void Function(String text) onFinal,
    required void Function() onSilence,
    required void Function(String error) onError,
    required void Function(double level) onLevel,
    void Function()? onTranscribing,
    bool usePhoneMic = false,
  }) async {
    listens++;
    if (script.isEmpty) return; // stays "listening" — the test ends here
    final next = script.removeAt(0);
    scheduleMicrotask(() => next == null ? onSilence() : onFinal(next));
  }

  @override
  Future<void> stop() async {}
  @override
  Future<void> cancel() async {}
}

class FakeMouth implements Mouth {
  final said = <String>[];
  @override
  String get engineName => 'fake';
  SpeechOutput lastOutput = SpeechOutput.normal;
  double? lastRate;

  @override
  Future<void> configure({
    required String language,
    required double rate,
    String? voice,
    SpeechOutput output = SpeechOutput.normal,
  }) async {
    lastOutput = output;
    lastRate = rate;
  }
  /// false = like earbuds-only speech that Android refused to route.
  bool canBeHeard = true;

  @override
  Future<bool> speak(String text, {void Function(int start, int end)? onWord}) async {
    said.add(text);
    onWord?.call(0, text.contains(' ') ? text.indexOf(' ') : text.length);
    return canBeHeard;
  }

  @override
  Future<void> stop() async {}

  final prepared = <String>[];
  @override
  Future<int> prepare(Iterable<String> texts) async {
    prepared.addAll(texts);
    return texts.length;
  }
}

class FakePhone implements Phone {
  final calls = <String>[];
  List<Person> people = const [Person('Ravi Sharma', '98765 43210'), Person('Mummy', '99999 00000')];

  @override
  Future<void> setAlarm(int hour, int minute, String label) async => calls.add('alarm $hour:$minute');
  @override
  Future<void> setTimer(int seconds, String label) async => calls.add('timer $seconds');
  @override
  Future<void> dial(String number) async => calls.add('dial $number');
  @override
  Future<void> whatsapp(String number, String text) async => calls.add('wa $number $text');
  @override
  Future<void> sms(String number, String text) async => calls.add('sms $number $text');
  @override
  Future<void> openUrl(String url) async => calls.add('url $url');
  @override
  Future<bool> openApp(String target) async {
    calls.add('open $target');
    return true;
  }

  @override
  Future<bool> torch(bool on) async {
    calls.add('torch $on');
    return true;
  }

  @override
  Future<({int level, bool charging})?> battery() async => (level: 82, charging: false);
  @override
  Future<List<Person>> findPeople(String query) async => rankPeople(people, query);

  // ── device abilities (DeviceBridge.kt on a real phone) ──
  bool clockCanDismiss = true;
  DateTime? next;
  bool hasDndAccess = true;
  bool somethingPaused = false;
  bool musicAppInstalled = true;
  Map<String, String> installedApps = const {'Angel One': 'com.msf.angelone', 'Hotstar': 'in.startv.hotstar'};
  int volumePercent = 40;

  @override
  Future<bool> dismissAlarm(int hour, int minute) async {
    calls.add('dismiss alarm $hour:$minute');
    return clockCanDismiss;
  }

  @override
  Future<void> showAlarms() async => calls.add('show alarms');
  @override
  Future<void> showTimers() async => calls.add('show timers');
  @override
  Future<DateTime?> nextAlarm() async => next;

  @override
  Future<bool> setRinger(String mode) async {
    calls.add('ringer $mode');
    return hasDndAccess || mode == 'vibrate' || mode == 'normal';
  }

  @override
  Future<void> openDndAccess() async => calls.add('open dnd access');

  @override
  Future<int?> volume(String action, {int? level}) async {
    calls.add('volume $action${level == null ? '' : ' $level'}');
    volumePercent = switch (action) {
      'up' => (volumePercent + 13).clamp(0, 100),
      'down' => (volumePercent - 13).clamp(0, 100),
      'max' => 100,
      'mute' => 0,
      'set' => level ?? volumePercent,
      _ => volumePercent,
    };
    return volumePercent;
  }

  @override
  Future<bool> media(String action) async {
    calls.add('media $action');
    return action != 'play' || somethingPaused;
  }

  @override
  Future<bool> playMusic(String query, {String? app}) async {
    calls.add('play "$query"${app == null ? '' : ' on $app'}');
    return musicAppInstalled;
  }

  @override
  Future<bool> openSetting(String which) async {
    calls.add('setting $which');
    return true;
  }

  @override
  Future<bool> navigate(String place) async {
    calls.add('navigate $place');
    return true;
  }

  @override
  Future<InstalledApp?> findApp(String name) async =>
      bestAppMatch([for (final e in installedApps.entries) (label: e.key, package: e.value)], name);
}

/// A model that answers from a script instead of running llama.cpp.
/// Each complete() pops the next scripted contract JSON; [prompts] records
/// what the brain sent, so tests can check memory/time made it in.
class FakeBrainRuntime implements BrainRuntime {
  FakeBrainRuntime(this.answers);
  final List<String> answers;
  final prompts = <String>[];
  bool _loaded = false;
  int loads = 0;

  @override
  bool get isLoaded => _loaded;

  @override
  Future<void> load(String modelPath, {int threads = 4, int contextSize = 4096}) async {
    loads++;
    _loaded = true;
  }

  @override
  Future<bool> warmPrefix(String prefix, String cacheFile) async => false;

  @override
  Future<BrainGeneration> complete(String prompt,
      {String? grammar, int maxTokens = 256, List<String> stop = const []}) async {
    prompts.add(prompt);
    final answer = answers.isEmpty ? '{"type":"reply","text":"..."}' : answers.removeAt(0);
    return BrainGeneration(answer, 40, 10, 12);
  }

  @override
  void cancel() {}

  @override
  Future<void> unload() async => _loaded = false;
}

/// Records what AERIS asked Android to do about a call; the test drives
/// [events] (ringing / answered / ended) itself.
class FakeCallBridge implements CallBridge {
  final eventController = StreamController<CallEvent>.broadcast();
  final actions = <String>[];
  final glows = <GlowState>[];
  bool answerWorks = true;
  bool rejectWorks = true;

  @override
  Stream<CallEvent> get events => eventController.stream;
  @override
  Future<void> startWatching() async => actions.add('start watching');
  @override
  Future<void> stopWatching() async => actions.add('stop watching');
  @override
  Future<bool> isWatching() async => true;
  @override
  Future<bool> answer({bool onSpeaker = false}) async {
    actions.add(onSpeaker ? 'answer on speaker' : 'answer');
    return answerWorks;
  }

  @override
  Future<bool> reject() async {
    actions.add('reject');
    return rejectWorks;
  }

  @override
  Future<bool> sendText(String number, String text) async {
    actions.add('sms $number: $text');
    return true;
  }

  @override
  Future<void> silenceRinger({Duration fade = Duration.zero}) async => actions.add('silence ringer');
  @override
  Future<void> restoreRinger({Duration fade = Duration.zero}) async =>
      actions.add(fade == Duration.zero ? 'restore ringer' : 'fade ringer back');
  /// The next glow() throws once (simulates an Android-side failure).
  bool failNextGlow = false;

  @override
  Future<void> glow(GlowState state) async {
    if (failNextGlow) {
      failNextGlow = false;
      throw StateError('overlay failed');
    }
    glows.add(state);
  }
  @override
  Future<void> glowLevel(double level) async {}
  /// What the phone reports when a call rings (default: ringer on, no earbuds).
  AudioSituation situation = const AudioSituation();
  @override
  Future<AudioSituation> audioSituation() async => situation;

  List<String> callers = const [];
  @override
  Future<List<String>> likelyCallers({int limit = 40}) async => callers.take(limit).toList();
  @override
  Future<bool> canDrawOverlays() async => true;
  @override
  Future<void> openOverlaySettings() async {}
}
