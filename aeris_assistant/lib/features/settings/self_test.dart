import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

import '../../app/scope.dart';
import '../../brain/router.dart' as brain;
import '../../ui/kit/controls.dart';
import '../../ui/tokens.dart';
import '../../voice/hindi_speech.dart';
import '../../voice/local/local_mouth.dart';
import '../../voice/local/model_store.dart';
import '../../voice/local/speech_worker.dart';
import '../../voice/local/voice_cache.dart';
import '../../voice/translit.dart';

/// On-phone self-test of the whole own-speech stack, with real numbers:
/// model load time, recognizer accuracy + latency on bundled Hinglish/English
/// command clips (scored as "would AERIS do the right thing"), and how fast
/// the JARVIS voice makes speech. Every line also goes to logcat with the
/// tag AERIS_SELFTEST so it can be read over adb.
class SelfTest {
  SelfTest(this.onLine, {this.name = '', this.voiceSpeed = LocalMouth.baseSpeed});
  final void Function(String line) onLine;
  final String name;

  /// The Settings speed (via [LocalMouth.speedFor]) — tests what AERIS really says.
  final double voiceSpeed;

  void _log(String s) {
    debugPrint('AERIS_SELFTEST $s');
    onLine(s);
  }

  static String _sig(brain.Plan p) {
    const keys = ['hour', 'minute', 'seconds', 'on', 'to', 'app', 'value', 'text'];
    return '${p.tool}${[for (final k in keys) if (p.args.containsKey(k)) '$k=${p.args[k]}'].join(',')}';
  }

  /// PCM16 mono WAV → float samples (16 kHz test clips).
  static Float32List _wav(ByteData b) {
    var off = 12;
    while (off + 8 <= b.lengthInBytes) {
      final id = String.fromCharCodes(b.buffer.asUint8List(b.offsetInBytes + off, 4));
      final size = b.getUint32(off + 4, Endian.little);
      if (id == 'data') {
        final n = size ~/ 2;
        final out = Float32List(n);
        for (var i = 0; i < n; i++) {
          out[i] = b.getInt16(off + 8 + i * 2, Endian.little) / 32768.0;
        }
        return out;
      }
      off += 8 + size + (size & 1);
    }
    return Float32List(0);
  }

  Future<void> run() async {
    final total = Stopwatch()..start();
    _log('START');

    // 1 — models
    final sw = Stopwatch()..start();
    final paths = await ModelStore.ensure();
    final worker = await SpeechWorker.get(paths);
    await worker.warm();
    _log('models ready in ${sw.elapsedMilliseconds} ms');

    // 2 — recognizer → router, on bundled clips
    final index = (jsonDecode(await rootBundle.loadString('assets/selftest/index.json')) as List).cast<Map>();
    const r = brain.Router();
    final now = DateTime(2026, 11, 16, 21, 4);
    var ok = 0, msSum = 0, audioMs = 0;
    for (final it in index) {
      final clip = _wav(await rootBundle.load('assets/selftest/${it['file']}'));
      audioMs += clip.length * 1000 ~/ 16000;
      final t = Stopwatch()..start();
      final raw = await worker.transcribe(clip);
      final ms = t.elapsedMilliseconds;
      msSum += ms;
      final heard = cleanTranscript(raw);
      final want = _sig(r.route(it['text'] as String, now: now));
      final got = _sig(r.route(heard, now: now));
      final pass = want == got;
      if (pass) ok++;
      _log('${pass ? 'PASS' : 'FAIL'} ${ms}ms "${it['text']}" heard "$heard"');
    }
    _log('RECOGNIZER $ok/${index.length} correct actions, avg ${msSum ~/ index.length} ms/command, '
        'RTF ${(msSum / audioMs).toStringAsFixed(2)}');

    // 3 — JARVIS voice speed
    const replies = [
      'Haan Shivang, boliye.',
      '6:30 a.m. ka alarm laga diya.',
      'Battery 82% hai, charging ho rahi hai.',
      'Abhi 9:04 p.m. ho rahe hain.',
      'Youtube khol raha hoon.',
      'Main AERIS hoon, aapka assistant. Isi phone pe chalta hoon.',
    ];
    final dir = (await getTemporaryDirectory()).path;
    var genMs = 0, speechMs = 0, first = 0;
    for (final (i, text) in replies.indexed) {
      final t = Stopwatch()..start();
      final ms = await worker.synth(toSpokenDevanagari(text),
          speed: voiceSpeed, lang: LocalMouth.modelLang, sid: LocalMouth.voiceSid, path: '$dir/selftest_$i.wav');
      final g = t.elapsedMilliseconds;
      if (i == 0) first = g;
      genMs += g;
      speechMs += ms;
      _log('VOICE ${g}ms to make ${ms}ms: "$text"');
    }
    _log('VOICE avg ${genMs ~/ replies.length} ms per reply, RTF ${(genMs / speechMs).toStringAsFixed(2)}, '
        'first reply ${first}ms');
    // 4 — how many common replies are already pre-made (play instantly)
    final cache = await VoiceCache.open();
    var ready = 0, chunks = 0;
    for (final phrase in commonReplies(name)) {
      for (final (_, s) in LocalMouth.sentences(phrase)) {
        chunks++;
        final key = VoiceCache.keyOf(toSpokenDevanagari(s.trim()), voiceSpeed, LocalMouth.modelLang, LocalMouth.voiceSid);
        if (cache.get(key) != null) ready++;
      }
    }
    _log('CACHE $ready/$chunks common reply chunks pre-made (instant), ${cache.size} phrases cached in total');
    _log('DONE in ${(total.elapsedMilliseconds / 1000).toStringAsFixed(1)} s');
  }
}

/// Bottom sheet that runs the test and shows the lines live.
class SelfTestSheet extends StatefulWidget {
  const SelfTestSheet({super.key});

  @override
  State<SelfTestSheet> createState() => _SelfTestSheetState();
}

class _SelfTestSheetState extends State<SelfTestSheet> {
  final _lines = <String>[];
  bool _running = false;

  Future<void> _run() async {
    setState(() {
      _running = true;
      _lines.clear();
    });
    try {
      await SelfTest((l) {
        if (mounted) setState(() => _lines.add(l));
      }, name: context.store.settings.name.trim(), voiceSpeed: LocalMouth.speedFor(context.store.settings.rate)).run();
    } catch (e) {
      debugPrint('AERIS_SELFTEST ERROR $e');
      if (mounted) setState(() => _lines.add('ERROR $e'));
    }
    if (mounted) setState(() => _running = false);
  }

  @override
  Widget build(BuildContext context) {
    final summary = _lines.where((l) => l.startsWith('RECOGNIZER') || l.startsWith('VOICE avg') || l.startsWith('models')).toList();
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.xl),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Self-test', style: T.heading),
          const SizedBox(height: S.xs),
          const Text('Runs 24 recorded commands through the on-phone recognizer and times the JARVIS voice. Nothing is sent anywhere; no alarms or messages are made.',
              style: T.bodyDim),
          const SizedBox(height: S.lg),
          for (final s in summary) Padding(padding: const EdgeInsets.only(bottom: S.xs), child: Text(s, style: T.mono.copyWith(color: C.text1))),
          SizedBox(
            height: 220,
            child: ListView(
              reverse: true,
              children: [for (final l in _lines.reversed) Text(l, style: T.mono.copyWith(fontSize: 10.5, color: l.startsWith('FAIL') ? C.amber : C.text2))],
            ),
          ),
          const SizedBox(height: S.lg),
          HudButton(
            label: _running ? 'Running…' : (_lines.isEmpty ? 'Run self-test' : 'Run again'),
            icon: Icons.science_outlined,
            onPressed: _running ? null : _run,
          ),
        ]),
      ),
    );
  }
}
