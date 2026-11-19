import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';

import '../../calls/call_phrases.dart';
import '../io.dart';
import '../hindi_speech.dart';
import 'model_store.dart';
import 'ringing_voice_player.dart';
import 'speech_worker.dart';
import 'voice_cache.dart';

/// Replies AERIS gives most often — pre-made at startup so they're instant.
/// Must match the executor/session wording exactly (cache is keyed on text).
List<String> commonReplies(String name) => [
      name.isEmpty ? 'Haan, boliye.' : 'Haan $name, boliye.',
      'Theek hai, bye!',
      'Koi baat nahi.',
      'Yaad rakh liya.',
      'Torch on.',
      'Torch off.',
      'Kis time ka alarm lagaun?',
      'Kitne time ka timer?',
      'Kisko call karun?',
      'Kya message bhejun?',
      'Message ready hai — bas send dabaiye.',
      'Theek hai, nahi bheja.',
      'Theek hai, rehne dete hain.',
      'Main badhiya hoon! Aap batao, kya karna hai?',
      'Ye mujhe abhi nahi aata. Google pe search karun?',
      'Google pe dhoondh raha hoon.',
      ...CallPhrases.premade, // incoming calls (lib/calls/call_assistant.dart)
    ];

/// The JARVIS voice — Supertonic 3 male voice 9 at 1.0× (picked by ear from
/// samples, 2026-11-17), generated on the phone. Hinglish replies are spoken
/// from Devanagari (hi mode) — the way the chosen sample was made — while the
/// screen keeps the Roman text. Sentence-pipelined: N+1 is synthesised while
/// N plays, so long replies start fast and never gap.
class LocalMouth implements Mouth {
  final _player = AudioPlayer(playerId: 'aeris-jarvis');
  double _speed = baseSpeed;
  bool _hindi = true;

  /// AERIS's only voice, everywhere (conversation, calls, previews):
  /// Supertonic 3 male voice 9 at normal pace — exactly
  /// build/voice_samples_natural/S1_Supertonic_male9_HINGLISH.wav, Shivang's
  /// final pick (2026-11-17; male 7 before that). The Settings speed slider
  /// scales [baseSpeed] through [speedFor].
  static const baseSpeed = 1.0;

  /// THE speed formula: the settings slider value → Supertonic speed
  /// (0.5 = 1.0× = the picked sample). Everything that speaks goes through it.
  static double speedFor(double settingsRate) => (baseSpeed * settingsRate / 0.5).clamp(0.6, 2.0);
  static const voiceSid = 9;

  /// Supertonic language for every reply — 'en', even for Devanagari Hinglish.
  /// That is how the chosen sample was really made (see tool/model_export/README).
  static const modelLang = 'en';
  int _gen = 0;
  final _timers = <Timer>[];
  Completer<void>? _playing;
  StreamSubscription<void>? _done;
  String? lastError;

  @override
  String get engineName => 'JARVIS · Supertonic voice $voiceSid (on this phone)';

  SpeechOutput? _output; // what the player is set up for (null = not yet)

  @override
  Future<void> configure({
    required String language,
    required double rate,
    String? voice,
    SpeechOutput output = SpeechOutput.normal,
  }) async {
    _speed = speedFor(rate);
    _hindi = language.startsWith('hi');
    if (output == SpeechOutput.normal && _output != SpeechOutput.normal) {
      await _player.setAudioContext(_normalAudio);
    }
    _output = output;
  }

  /// Normal conversation: media channel, other apps' audio ducks while AERIS talks.
  static final _normalAudio = AudioContext(
    android: const AudioContextAndroid(
      contentType: AndroidContentType.speech,
      usageType: AndroidUsageType.media,
      audioFocus: AndroidAudioFocus.gainTransientMayDuck,
    ),
  );

  /// The ringing outputs go through Android's own player (it can pick the
  /// earbuds and doesn't wait for audio focus) — see [SpeechOutput].
  bool get _ringing => _output == SpeechOutput.ringingAloud || _output == SpeechOutput.ringingEarbudsOnly;

  /// Split into sentences, keeping each one's offset in the full text.
  static List<(int, String)> sentences(String text) {
    // "12:46 a.m." is one unit, not three sentences: hide its dots while
    // splitting (same-length stand-in keeps every offset exact), then restore.
    const dot = '\u2024';
    final masked = text.replaceAllMapped(
        RegExp(r'\b([ap])\.m\.', caseSensitive: false), (m) => '${m[1]}${dot}m$dot');
    String unmask(String s) => s.replaceAll(dot, '.');
    final out = <(int, String)>[];
    final re = RegExp(r'[^.!?।]+[.!?।]*');
    for (final m in re.allMatches(masked)) {
      final s = unmask(m[0]!);
      if (s.trim().isEmpty) continue;
      out.add((m.start, s));
    }
    if (out.isEmpty) return [(0, text)];
    // the first chunk decides how soon AERIS starts talking — split a long
    // first sentence at its first comma so audio starts sooner
    final (start, first) = out.first;
    final comma = first.indexOf(', ');
    if (first.length > 32 && comma > 6 && comma < first.length - 8) {
      out
        ..removeAt(0)
        ..insertAll(0, [(start, first.substring(0, comma + 1)), (start + comma + 2, first.substring(comma + 2))]);
    }
    return out;
  }

  /// Even-by-length word timings inside one sentence of [ms] audio.
  static List<(int, int, int)> wordTimes(String sentence, int base, int ms) {
    final words = RegExp(r'\S+').allMatches(sentence).toList();
    if (words.isEmpty) return const [];
    final total = words.fold<int>(0, (a, w) => a + w[0]!.length + 1);
    final speechMs = ms * 0.9; // leave room for the short tail silence
    var t = ms * 0.03;
    final out = <(int, int, int)>[];
    for (final w in words) {
      out.add((t.round(), base + w.start, base + w.end));
      t += speechMs * (w[0]!.length + 1) / total;
    }
    return out;
  }

  @override
  Future<bool> speak(String text, {void Function(int start, int end)? onWord}) async {
    await stop();
    final gen = ++_gen;
    if (text.trim().isEmpty) return true;
    final parts = sentences(text);
    final clock = Stopwatch()..start();
    var next = _chunk(parts[0].$2.trim());
    for (var i = 0; i < parts.length; i++) {
      final String path;
      final int ms;
      try {
        (path, ms) = await next;
      } catch (e) {
        lastError = '$e';
        debugPrint('JARVIS voice failed: $e');
        return false;
      }
      if (gen != _gen) return false;
      _trace('sentence ${i + 1}/${parts.length} ready at ${clock.elapsedMilliseconds} ms ($ms ms of audio, ${_output?.name})');
      if (i + 1 < parts.length) next = _chunk(parts[i + 1].$2.trim()); // overlap with playback
      if (_ringing) {
        final played = await RingingVoicePlayer.play(path,
            earbudsOnly: _output == SpeechOutput.ringingEarbudsOnly, timeout: Duration(milliseconds: ms + 3000));
        _trace('sentence ${i + 1} ${played ? 'played' : 'NOT played'} at ${clock.elapsedMilliseconds} ms');
        if (!played) return false; // e.g. earbuds refused — never fall back to the speaker
        if (gen != _gen) return false;
        continue;
      }
      final done = Completer<void>();
      _playing = done;
      _done = _player.onPlayerComplete.listen((_) {
        if (!done.isCompleted) done.complete();
      });
      await _player.play(DeviceFileSource(path), mode: PlayerMode.mediaPlayer);
      if (onWord != null) {
        for (final (at, s, e) in wordTimes(parts[i].$2, parts[i].$1, ms)) {
          _timers.add(Timer(Duration(milliseconds: at), () {
            if (gen == _gen) onWord(s, e);
          }));
        }
      }
      var finished = true;
      await done.future.timeout(Duration(milliseconds: ms + 2500), onTimeout: () => finished = false);
      _trace('sentence ${i + 1} ${finished ? 'played' : 'NOT confirmed played (timed out)'} at ${clock.elapsedMilliseconds} ms');
      _clear();
      if (gen != _gen) return false;
    }
    return true;
  }

  /// One logcat line per sentence (tag AERIS_VOICE): how long the voice took
  /// to make and whether the player confirmed playing it.
  static void _trace(String step) => debugPrint('AERIS_VOICE $step');

  /// One chunk of speech: from the persistent cache if AERIS has said it
  /// before (instant), otherwise synthesised once and kept.
  Future<(String, int)> _chunk(String shown) async {
    final cache = await VoiceCache.open();
    final spoken = _hindi ? toSpokenDevanagari(shown) : shown;
    const lang = modelLang;
    final key = VoiceCache.keyOf(spoken, _speed, lang, voiceSid);
    final hit = cache.get(key);
    if (hit != null) return hit;
    final worker = await SpeechWorker.get(await ModelStore.ensure());
    final ms = await worker.synth(spoken, speed: _speed, lang: lang, sid: voiceSid, path: cache.tempPath(key));
    return cache.put(key, ms);
  }

  /// Make [texts] ahead of time (no playback), so they're instant later.
  /// Skips anything already cached; gentle pauses keep the phone cool.
  @override
  Future<int> prepare(Iterable<String> texts) async {
    var made = 0;
    for (final t in texts) {
      for (final (_, s) in sentences(t)) {
        final cache = await VoiceCache.open();
        final spoken = _hindi ? toSpokenDevanagari(s.trim()) : s.trim();
        if (cache.get(VoiceCache.keyOf(spoken, _speed, modelLang, voiceSid)) != null) continue;
        await _chunk(s.trim());
        made++;
        await Future<void>.delayed(const Duration(milliseconds: 400));
      }
    }
    return made;
  }

  void _clear() {
    for (final t in _timers) {
      t.cancel();
    }
    _timers.clear();
    _done?.cancel();
    _done = null;
    final p = _playing;
    _playing = null;
    if (p != null && !p.isCompleted) p.complete();
  }

  @override
  Future<void> stop() async {
    _gen++;
    _clear();
    try {
      await _player.stop();
    } catch (_) {}
    if (_ringing) await RingingVoicePlayer.stop(); // e.g. the user picked up by touch
  }
}
