// Translates the brain's answer (a "contract" JSON object) into something this
// app already knows how to do: a [Plan] for the executor, or words to speak.
//
// Pure function, no I/O — every mapping is covered by test/brain_bridge_test.dart.
//
// The brain is trained on 37 tools (aeris_brain/schema/tools.json); this app
// can run a subset today. A tool it can't run becomes an honest
// "I can't do that yet" ([BrainCannotDoYet]) instead of a wrong action, and is
// logged so we know what to build next.
import '../../core/models.dart';
import '../memory_search.dart';
import '../parse.dart';
import '../router.dart';

/// What the session should do with the brain's answer.
sealed class BrainAction {
  const BrainAction();
}

/// Run this plan through the normal executor (approval rules still apply).
class BrainRunsPlan extends BrainAction {
  const BrainRunsPlan(this.plan);
  final Plan plan;
}

/// Speak [text]. If [expectsAnswer] is true the brain asked a question, so the
/// user's next utterance is the answer and goes straight back to the brain.
class BrainSpeaks extends BrainAction {
  const BrainSpeaks(this.text, {this.expectsAnswer = false});
  final String text;
  final bool expectsAnswer;
}

/// The brain picked a tool this app can't run yet.
class BrainCannotDoYet extends BrainAction {
  const BrainCannotDoYet(this.toolName);
  final String toolName;
}

/// Turns a *validated* contract object into a [BrainAction].
///
/// [memories] lets `recall` answer from the memory store; [now] resolves
/// spoken alarm times ("kal subah 7 baje") to a clock time.
BrainAction actionFromContract(
  Map<String, dynamic> contract, {
  List<Memory> memories = const [],
  DateTime? now,
}) {
  switch (contract['type']) {
    case 'reply':
      return BrainSpeaks('${contract['text']}'.trim());
    case 'ask':
      return BrainSpeaks('${contract['text']}'.trim(), expectsAnswer: true);
    case 'escalate':
      // Needs the internet or a bigger brain → offer a web search (asks first).
      return BrainRunsPlan(Plan(
        'search',
        {'q': '${contract['query']}', 'reason': '${contract['reason']}'},
        true,
      ));
    case 'plan':
      return const BrainCannotDoYet('plan'); // multi-app automation isn't built here yet
    case 'tool_call':
      // One action per turn: the first call. Multi-call turns are rare in
      // speech, and protocols already cover "one phrase, many actions".
      final firstCall = ((contract['calls'] as List).first as Map).cast<String, dynamic>();
      final toolArgs = (firstCall['args'] as Map? ?? const {}).cast<String, dynamic>();
      return _actionForTool('${firstCall['name']}', toolArgs, memories, now ?? DateTime.now());
  }
  return const BrainCannotDoYet('unknown');
}

BrainAction _actionForTool(
  String toolName,
  Map<String, dynamic> toolArgs,
  List<Memory> memories,
  DateTime now,
) {
  String argText(String key) => '${toolArgs[key] ?? ''}'.trim();
  String contactOrNumber() => argText('contact').isNotEmpty ? argText('contact') : argText('number');

  switch (toolName) {
    case 'flashlight':
      return BrainRunsPlan(Plan('torch', {'on': argText('state') != 'off'}));

    case 'battery_status':
      return const BrainRunsPlan(Plan('battery'));

    case 'date_time':
      return BrainRunsPlan(Plan(argText('what') == 'time' ? 'time' : 'date'));

    case 'calculate':
      final math = parseMath(normalize(argText('expression')));
      if (math == null) return const BrainCannotDoYet('calculate');
      return BrainRunsPlan(Plan('math', {'expr': math.expr, 'value': math.value}));

    case 'set_alarm':
      final when = normalize('${argText('days')} ${argText('time')}');
      final clock = parseClock(when, now);
      if (clock == null) return const BrainRunsPlan(Plan('clarify', {'for': 'alarm'}));
      return BrainRunsPlan(Plan('alarm', {
        'hour': clock.hour,
        'minute': clock.minute,
        'spoken': clock.spoken,
        if (argText('label').isNotEmpty) 'label': argText('label'),
      }));

    case 'set_reminder':
      // The router knows every way of saying "when" — reuse it.
      final reminder = const Router().route('${argText('when')} yaad dilana ki ${argText('text')}', now: now);
      return reminder.tool == 'remind' || reminder.tool == 'clarify'
          ? BrainRunsPlan(reminder)
          : const BrainCannotDoYet('set_reminder');

    case 'set_timer':
      final seconds = parseDuration(normalize(argText('duration')));
      if (seconds == null) return const BrainRunsPlan(Plan('clarify', {'for': 'timer'}));
      return BrainRunsPlan(Plan('timer', {'seconds': seconds}));

    case 'call':
      if (argText('app') == 'whatsapp' || toolArgs['video'] == true) {
        return const BrainCannotDoYet('call (WhatsApp / video)');
      }
      final callee = contactOrNumber();
      if (callee.isEmpty) return const BrainRunsPlan(Plan('clarify', {'for': 'call'}));
      return BrainRunsPlan(Plan('call', {'to': callee}));

    case 'send_message':
      if (argText('app') == 'telegram') return const BrainCannotDoYet('send_message (Telegram)');
      // The brain sets `app` only when the user said it; plain "message" = SMS,
      // the same default the rule router uses.
      final messagingApp = argText('app') == 'whatsapp' ? 'whatsapp' : 'sms';
      // Missing who or what → ask, never show an empty "send?" panel.
      if (contactOrNumber().isEmpty) {
        return BrainRunsPlan(Plan('clarify', {'for': 'message_to', 'body': argText('message'), 'app': messagingApp}));
      }
      if (argText('message').isEmpty) {
        return BrainRunsPlan(Plan('clarify', {'for': 'message', 'to': contactOrNumber(), 'app': messagingApp}));
      }
      return BrainRunsPlan(Plan(
        'message',
        {'to': contactOrNumber(), 'body': argText('message'), 'app': messagingApp},
        true, // nothing leaves the phone without the user's "haan"
      ));

    case 'open_app':
      final appName = normalize(argText('app')).replaceAll(RegExp(r'\s+(app|application)$'), '');
      return BrainRunsPlan(Plan('open', {'app': appName, 'target': knownApps[appName]}));

    case 'camera':
      return BrainRunsPlan(Plan('open', {'app': 'camera', 'target': knownApps['camera']}));

    case 'web_search':
      if (argText('engine') == 'youtube') {
        return BrainRunsPlan(Plan('open', {'app': 'youtube', 'target': knownApps['youtube']}));
      }
      return BrainRunsPlan(Plan('search', {'q': argText('query')}));

    case 'remember':
    case 'create_note':
      final fact = argText('fact').isNotEmpty ? argText('fact') : argText('text');
      return BrainRunsPlan(Plan('remember', {'text': fact}));

    case 'recall':
      final bestMatch = bestMatchingMemory(argText('query'), memories);
      // text: null → the executor says "you haven't told me that yet".
      return BrainRunsPlan(Plan('recall', {'id': bestMatch?.id, 'text': bestMatch?.text}));

    case 'volume':
      final action = argText('action').isEmpty ? 'up' : argText('action');
      final level = int.tryParse(argText('level'));
      return BrainRunsPlan(Plan('volume', {'action': action, if (action == 'set') 'level': (level ?? 50).clamp(0, 100)}));

    case 'media_control':
      final action = switch (argText('action')) { 'stop' => 'pause', '' => 'toggle', final other => other };
      return BrainRunsPlan(Plan('media', {'action': action}));

    case 'play_music':
      final app = argText('app');
      return BrainRunsPlan(Plan('play', {'q': argText('query'), if (app.isNotEmpty && app != 'default') 'app': app}));

    case 'toggle_setting':
      final setting = argText('setting');
      if (setting == 'dnd') {
        return BrainRunsPlan(Plan('ringer', {'mode': argText('state') == 'off' ? 'normal' : 'silent'}));
      }
      return BrainRunsPlan(Plan('setting', {'which': setting, 'on': argText('state') != 'off'}));

    case 'open_settings':
      return BrainRunsPlan(Plan('setting', {'which': argText('page').isEmpty ? 'main' : argText('page')}));

    case 'navigate_to':
      final destination = argText('destination');
      if (destination.isEmpty) return const BrainCannotDoYet('navigate_to');
      final place = switch (normalize(destination)) {
        'ghar' || 'home' => 'Home',
        'office' || 'work' || 'daftar' => 'Work',
        _ => destination,
      };
      return BrainRunsPlan(Plan('navigate', {'place': place}));

    case 'end_conversation':
    case 'cancel_task':
      return const BrainRunsPlan(Plan('end'));
  }
  return BrainCannotDoYet(toolName);
}
