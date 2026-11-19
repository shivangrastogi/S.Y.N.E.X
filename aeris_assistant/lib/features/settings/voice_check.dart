import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import '../../voice/hindi_speech.dart';
import '../../voice/local/local_mouth.dart';
import '../../voice/local/model_store.dart';
import '../../voice/local/speech_worker.dart';

/// Voice check, started over adb (no taps needed):
///   adb shell am start -n com.aeris.aeris_assistant/.MainActivity --es route /voicecheck
/// Makes the same sentence as the laptop sample S1_Supertonic_male9_HINGLISH.wav
/// with the app's exact settings and saves WAVs to the app's external files dir
/// (adb pull /sdcard/Android/data/com.aeris.aeris_assistant/files/voicecheck/).
abstract final class VoiceCheck {
  /// Exactly the text the laptop sample was made from.
  static const sampleDevanagari = 'नमस्ते शिवांग! कल सुबह साढ़े छह बजे का अलार्म लगा दिया है। और कुछ चाहिए?';

  /// The same sentence as AERIS would write it on screen.
  static const sampleRoman = 'Namaste Shivang! Kal subah 6:30 a.m. ka alarm laga diya hai. Aur kuch chahiye?';

  /// [rate]: the Settings speed — the check makes exactly what AERIS says.
  static Future<void> run({double rate = 0.5}) async {
    final speed = LocalMouth.speedFor(rate);
    final ext = await getExternalStorageDirectory();
    if (ext == null) return;
    final dir = Directory('${ext.path}/voicecheck')..createSync(recursive: true);
    final worker = await SpeechWorker.get(await ModelStore.ensure());
    await worker.warm();
    final roman = toSpokenDevanagari(sampleRoman);
    for (final (name, text) in [('phone_same_text', sampleDevanagari), ('phone_app_text', roman)]) {
      final t = Stopwatch()..start();
      final ms = await worker.synth(text,
          speed: speed, lang: LocalMouth.modelLang, sid: LocalMouth.voiceSid, path: '${dir.path}/$name.wav');
      debugPrint('AERIS_VOICECHECK $name ${ms}ms audio made in ${t.elapsedMilliseconds}ms text="$text"');
    }
    debugPrint('AERIS_VOICECHECK DONE sid=${LocalMouth.voiceSid} speed=$speed dir=${dir.path}');
  }
}
