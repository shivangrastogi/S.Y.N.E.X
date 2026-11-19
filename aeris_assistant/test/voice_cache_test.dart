import 'package:aeris_assistant/brain/executor.dart';
import 'package:aeris_assistant/brain/router.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:aeris_assistant/voice/local/local_mouth.dart';
import 'package:aeris_assistant/voice/local/voice_cache.dart';
import 'package:aeris_assistant/calls/call_phrases.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  test('every pre-made phrase is something AERIS really says (cache is keyed on exact text)', () async {
    final store = Store.memory()..settings = const Settings(name: 'Shivang', onboarded: true);
    final exec = Executor(FakePhone(), store);
    final said = <String>{
      for (final tool in ['greet', 'end', 'thanks', 'remember', 'howareyou'])
        (await exec.run(Plan(tool, tool == 'remember' ? const {'text': 'x'} : const {}))).reply,
      (await exec.run(const Plan('torch', {'on': true}))).reply,
      (await exec.run(const Plan('torch', {'on': false}))).reply,
      (await exec.run(const Plan('message', {'number': '1', 'body': 'b', 'app': 'whatsapp'}))).reply,
      (await exec.run(const Plan('search', {'q': 'x'}))).reply,
      for (final f in ['alarm', 'timer', 'call', 'message']) exec.clarify(Plan('clarify', {'for': f})),
      exec.approval(const Plan('search', {'q': 'x', 'fallback': true}, true)).question,
      'Theek hai, nahi bheja.', // session.dart, message approval cancelled
      'Theek hai, rehne dete hain.', // session.dart, search approval cancelled
      ...CallPhrases.premade, // call_assistant.dart: spoken as their own sentences
    };
    for (final phrase in commonReplies('Shivang')) {
      expect(said, contains(phrase), reason: 'pre-made "$phrase" is never said → wasted cache entry');
    }
  });

  test('cache key changes with anything that changes the audio', () {
    final k = VoiceCache.keyOf('हाँ', 1.35, 'hi', 9);
    expect(k.length, 16);
    expect(VoiceCache.keyOf('हाँ', 1.35, 'hi', 9), k); // stable
    expect(VoiceCache.keyOf('हाँ', 1.40, 'hi', 9), isNot(k));
    expect(VoiceCache.keyOf('हाँ', 1.35, 'en', 9), isNot(k));
    expect(VoiceCache.keyOf('हाँ', 1.35, 'hi', 6), isNot(k));
    expect(VoiceCache.keyOf('हा', 1.35, 'hi', 9), isNot(k));
  });
}
