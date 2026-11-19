import 'package:aeris_assistant/calls/call_commands.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('what the user says while the phone rings', () {
    void expectChoice(CallChoice? expected, List<String> phrases) {
      for (final phrase in phrases) {
        expect(callChoiceFrom(phrase), expected, reason: '"$phrase"');
      }
    }

    test('answer', () {
      expectChoice(CallChoice.answer, [
        'uthao', 'utha lo', 'haan uthao', 'pick up', 'answer it', 'haan', 'ok', 'uthao na', // "na" = please
        'baat karo', 'receive karo', 'mat kaato', // "don't cut" = answer
      ]);
    });

    test('answer on speaker', () {
      expectChoice(CallChoice.answerOnSpeaker, ['speaker pe uthao', 'speaker pe daal do', 'loudspeaker', 'mat kaato speaker pe']);
    });

    test('decline', () {
      expectChoice(CallChoice.decline, [
        'kaat do', 'kaato', 'cut kar do', 'reject', 'decline', 'nahi', 'mat uthao', // "mat" wins over "uthao"
        'baad mein', 'abhi nahi', 'busy hoon bolo', 'no', 'end karo',
      ]);
    });

    test('anything else → ask again', () {
      expectChoice(null, ['', 'kaun hai', 'hmm', 'Ravi']);
    });
  });
}
