// What the user said while the phone rings → answer, answer on speaker, or
// decline. Pure, so every phrasing is unit-tested (test/call_commands_test.dart).
import '../brain/parse.dart';

enum CallChoice { answer, answerOnSpeaker, decline }

// "mat kaato" = don't cut = answer. Checked before declining.
final _dontDecline = RegExp(r'\bmat (kaat|kaato|kato|kat|cut|reject)');
// Declining is checked before answering: "mat uthao" contains "uthao".
// No bare "na" — "uthao na" means "please pick up".
final _decline = RegExp(
  r'\b(kaat|kaato|kaat do|kat do|kato|cut|reject|decline|end|band kar|band karo|nahi|nahin|no|mat|'
  r'baad mein|baad me|later|busy|abhi nahi|ignore|chhodo|rehne do|rahne do)\b',
);
final _answer = RegExp(
  r'\b(utha|uthao|utha lo|uthalo|utha do|uthana|pick|pick up|pickup|answer|receive|accept|haan|han|ha|haa|'
  r'yes|yeah|ok|okay|theek hai|baat karo|baat karni hai|lagao|connect|jod do)\b',
);
final _speaker = RegExp(r'\b(speaker|loudspeaker|loud speaker|speaker pe|speaker par)\b');

/// Null when the sentence isn't clearly one of the three (AERIS asks again).
CallChoice? callChoiceFrom(String said) {
  final text = normalize(said);
  if (text.isEmpty) return null;
  if (_dontDecline.hasMatch(text)) return _speaker.hasMatch(text) ? CallChoice.answerOnSpeaker : CallChoice.answer;
  if (_decline.hasMatch(text)) return CallChoice.decline;
  if (_speaker.hasMatch(text)) return CallChoice.answerOnSpeaker; // "speaker pe" alone means answer
  if (_answer.hasMatch(text)) return CallChoice.answer;
  return null;
}
