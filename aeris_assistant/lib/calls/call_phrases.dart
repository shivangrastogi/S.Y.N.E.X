// The words AERIS says during an incoming call (lib/calls/call_assistant.dart).
// No imports on purpose: the voice cache pre-makes the fixed lines.

/// Everything AERIS says during a call, in one place (and pre-made in the
/// voice cache where the text is fixed — see `commonReplies`).
class CallPhrases {
  const CallPhrases(this.hinglish);
  final bool hinglish;

  String _pick(String hinglishText, String englishText) => hinglish ? hinglishText : englishText;

  String announce(String? callerName) => callerName == null
      ? '${_pick(unknownCallerHi, 'Call from an unknown number.')} ${question()}'
      // short on purpose: the name sentence is made on the phone while it
      // rings (cost grows with length); the question is pre-made
      : '${_pick('$callerName ka call.', 'Call from $callerName.')} ${question()}';
  String question() => _pick(questionHi, 'Answer or decline?');
  String offerText(String callerName) => _pick(
      '$callerName ko message bhejun ki baad mein baat karte hain?', 'Shall I text $callerName that you\'ll call back?');
  String textMessage() => _pick(messageHi, "Can't talk right now, I'll call you back soon.");
  String textSent() => _pick(sentHi, 'Sent.');
  String textFailed() => _pick('Message nahi ja paaya.', "The message couldn't be sent.");

  // Fixed Hinglish lines, pre-made in the voice cache so they play instantly.
  static const unknownCallerHi = 'Ek anjaan number se call aa raha hai.';
  static const questionHi = 'Uthaun ya kaatun?';
  static const sentHi = 'Bhej diya.';
  // Gender-neutral on purpose: it is sent in the user's name.
  static const messageHi = 'Abhi busy hoon, thodi der mein baat karte hain.';
  static const premade = [unknownCallerHi, questionHi, sentHi];
}
