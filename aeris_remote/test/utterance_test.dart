// Utterance stitching rules: a pause mid-command must not split it.
import 'package:flutter_test/flutter_test.dart';
import 'package:aeris_remote/assistant/utterance.dart';

void main() {
  test('join stitches segments and drops Android re-sends', () {
    expect(Utterance.join('', 'hi jarvis'), 'hi jarvis');
    expect(Utterance.join('hi jarvis', 'ek image banao'),
        'hi jarvis ek image banao');
    expect(Utterance.join('ek image banao', 'image banao'), 'ek image banao');
    expect(Utterance.join('ek image', 'ek image banao'), 'ek image banao');
    expect(Utterance.join('torch on karo', ''), 'torch on karo');
  });

  test('mid-thought endings wait longer', () {
    for (final t in [
      'Hi Jarvis',
      'hey aeris',
      'ek image banao aur',
      'kitchen mein khade aadmi ki image banao phir',
      'ravi ko',
      'firstly',
      'umm',
    ]) {
      expect(Utterance.dangling(t), isTrue, reason: t);
      expect(Utterance.holdFor(t), Utterance.holdDangling, reason: t);
    }
    for (final t in [
      'torch on karo',
      'ravi ko whatsapp pe bhejo',
      'aaj ka weather kya hai',
      'ek sunset ki photo banao',
    ]) {
      expect(Utterance.dangling(t), isFalse, reason: t);
      expect(Utterance.holdFor(t), Utterance.hold, reason: t);
    }
  });

  test('one-word replies and pending yes/no act immediately', () {
    for (final t in ['haan', 'bas', 'bye', 'Stop', 'nahi', 'theek hai']) {
      expect(Utterance.commitNow(t), isTrue, reason: t);
    }
    expect(Utterance.commitNow('haan bhej do'), isFalse);
    expect(Utterance.commitNow('haan bhej do', awaitingYesNo: true), isTrue);
    expect(Utterance.commitNow('torch on karo'), isFalse);
    expect(Utterance.commitNow(''), isFalse);
  });
}
