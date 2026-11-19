// Phase 10 — the phone agent. AERIS uses other apps the way a person would:
// "Gemini se kitchen mein khade aadmi ki image banao aur Ravi ko WhatsApp pe
// bhejo" → open Gemini, type the prompt, wait for the image, save it, open
// Ravi's WhatsApp chat with it attached, tap Send.
//
// Two Gemini roles (CloudBrain.json):
//   plan()  — once per request: is this a phone TASK at all? which installed
//             apps? does it message someone (→ the caller confirms first)?
//   run()   — a loop: read the screen as numbered elements (accessibility
//             dumpUi) → ask for ONE next action → do it → read again … until
//             "done"/"fail", a step cap, or a time cap.
//
// Everything that touches the phone goes through [AgentDevice] and the LLM
// through [AgentBrain], so test/phone_agent_test.dart drives the real loop
// with a fake phone + scripted brain (no device, no network).
import 'package:permission_handler/permission_handler.dart';
import 'package:url_launcher/url_launcher.dart';
import 'accessibility_bridge.dart';
import '../core/aeris_log.dart';
import 'app_launcher.dart';
import 'cloud_brain.dart';
import '../core/lang.dart';
import 'phone_skills.dart';

typedef AgentBrain = Future<Map<String, dynamic>> Function(
    String system, String prompt);

/// The phone, as the agent sees it.
abstract class AgentDevice {
  Future<String> screen();
  Future<bool> tap(int id);
  Future<bool> longPress(int id);
  Future<bool> type(int id, String text);
  Future<bool> enter();
  Future<bool> scroll(bool forward);
  Future<bool> global(String which);
  Future<bool> openApp(String name);
  Future<List<String>> apps();
  Future<List<(String, String)>> contacts(String name);
  Future<String> whatsappLatestImage(String phone);
  Future<bool> whatsappChat(String phone, String text);
  Future<String?> skill(String command);
  Future<void> wait(Duration d);
}

class AgentPlan {
  final bool isTask;
  final String summary; // spoken, in Lang.replyLanguage
  final List<String> steps;
  final bool messagesSomeone;
  final String recipient;
  const AgentPlan(this.isTask, this.summary, this.steps, this.messagesSomeone,
      this.recipient);

  factory AgentPlan.fromJson(Map<String, dynamic> j) => AgentPlan(
        j['is_task'] == true,
        (j['summary'] ?? '').toString().trim(),
        [for (final s in (j['steps'] as List? ?? const [])) s.toString()],
        j['messages_someone'] == true,
        (j['recipient'] ?? '').toString().trim(),
      );
}

class AgentResult {
  final bool ok;
  final String summary; // spoken, in Lang.replyLanguage
  final int steps;
  const AgentResult(this.ok, this.summary, this.steps);
}

class PhoneAgent {
  final AgentDevice device;
  final AgentBrain brain;
  final int maxSteps;
  final Duration timeLimit;
  final Duration settle; // let the UI update after an action

  PhoneAgent(
      {AgentDevice? device,
      AgentBrain? brain,
      this.maxSteps = 30,
      this.timeLimit = const Duration(minutes: 5),
      this.settle = const Duration(milliseconds: 1200)})
      : device = device ?? AndroidAgentDevice(),
        brain = brain ?? CloudBrain.json;

  // ── which utterances are worth a planner call ──────────────────────
  // Cheap pre-filter only: the planner makes the real decision (is_task),
  // and anything it rejects falls through to the normal tiers unchanged.
  static final _chain = RegExp(
      r'\b(and then|then|after that|firstly|first of all|uske baad|iske baad|'
      r'aur phir|phir|fir|baad mein)\b(?!\s*se\b)');
  static final _make = RegExp(
      r'\b(generate|create|make|draw|bana|banao|banwa|banwao|bana do|'
      r'banake|bana ke)\b');
  static final _media = RegExp(
      r'\b(image|images|photo|photos|picture|pic|pics|tasveer|wallpaper|'
      r'drawing|poster|logo)\b');
  static final _sendOn = RegExp(
      r'\b(bhejo|bhej do|bhej de|send|share)\b.*\b(whatsapp|whats app|'
      r'telegram|instagram|mail|gmail|sms)\b|'
      r'\b(whatsapp|whats app|telegram|instagram|mail|gmail)\b.*'
      r'\b(bhejo|bhej do|bhej de|send|share)\b');
  static final _explicit =
      RegExp(r'\b(khud (se )?karo|agent mode|tum karo|step by step karo)\b');

  /// True when [text] looks like a multi-step phone task rather than a
  /// one-shot skill or a question.
  static bool looksLikeTask(String text) {
    final s = text.toLowerCase();
    if (_explicit.hasMatch(s)) return true;
    final makesMedia = _make.hasMatch(s) && _media.hasMatch(s);
    if (makesMedia) return true;
    // "X ko whatsapp pe hello bolo" stays a Tier-1 skill; a chain or a
    // generated thing being sent is what needs the agent.
    return _chain.hasMatch(s) && (_sendOn.hasMatch(s) || _verbCount(s) >= 2);
  }

  /// The user's go-ahead for a parked plan: a yes word and no no word
  /// ("ok mat karo" is a no).
  static bool isYes(String text) {
    final s = text.toLowerCase();
    final yes = RegExp(r'\b(haan|han|haa|ha|yes|yeah|yep|ok|okay|theek|thik|'
            r'kar do|karo|bhejo|bhej do|go|go ahead|do it|send it|sure|chalo)\b')
        .hasMatch(s);
    final no = RegExp(r"\b(nahi|nahin|nai|na|no|nope|mat|cancel|ruko|rehne do|don't|dont|stop)\b")
        .hasMatch(s);
    return yes && !no;
  }

  static int _verbCount(String s) => RegExp(
          r'\b(kholo|open|karo|bhejo|send|search|dhundo|play|chalao|likho|'
          r'type|banao|generate|call|save|download|share|set|lagao)\b')
      .allMatches(s)
      .length;

  // ── planning ───────────────────────────────────────────────────────
  static const _planSystem = '''
You are the planner of AERIS, an Android phone agent. The user speaks Hinglish or English.
Decide whether the request is a TASK to carry out on the phone by operating
apps, or just a question / chat (not a task).

Return ONLY this JSON:
{"is_task": bool, "summary": string, "steps": [string], "messages_someone": bool, "recipient": string}

- summary: ONE short sentence in {LANG} for text-to-speech saying what you
  will do, as a statement, e.g. "Gemini se kitchen mein khade aadmi ki image
  banwa ke Ravi ko WhatsApp pe bhejunga." (Hinglish) or "I'll make an image
  of a man in a kitchen with Gemini and send it to Ravi on WhatsApp."
  (English).
- steps: 2-8 short concrete steps that name the apps to use, chosen ONLY from
  INSTALLED APPS. To generate images, text or answers, use an installed AI
  app (the one the user named; else Gemini; else ChatGPT; else Copilot / Meta
  AI). Sending an image on WhatsApp: save/download it in the AI app, then
  open the contact's WhatsApp chat with it attached and tap Send.
- messages_someone: true if any step sends a message, file or image to a
  person (WhatsApp, SMS, email, Telegram, Instagram...). recipient = who.
- If a needed app is NOT installed: is_task true, steps [], and the summary
  says in {LANG} what is missing.
- Never plan payments, purchases, deleting data or changing passwords.
''';

  /// Ask the planner about [goal]. Null if the brain is unreachable.
  Future<AgentPlan?> plan(String goal) async {
    final apps = await device.apps();
    final prompt = 'REQUEST: $goal\n\nINSTALLED APPS: ${apps.join(', ')}';
    try {
      return AgentPlan.fromJson(await brain(_lang(_planSystem), prompt));
    } catch (e) {
      AerisLog.add('agent', 'plan failed: $e');
      return null;
    }
  }

  /// Fill the reply language into a system prompt.
  static String _lang(String system) =>
      system.replaceAll('{LANG}', Lang.replyLanguage);

  // ── the loop ───────────────────────────────────────────────────────
  static const _stepSystem = '''
You are AERIS, operating an Android phone through accessibility to finish
the user's GOAL. Each turn you get the GOAL, the PLAN, the HISTORY of your
actions with their results, and the CURRENT SCREEN: first line "app: <package>",
then one line per element: [id] Class "label" actions. Use those ids.

Reply with ONE JSON object: {"thought": "<short reasoning>", "action": "<name>", ...args}
Actions:
  {"action":"open_app","app":"Gemini"}          launch an installed app by name
  {"action":"tap","id":7}
  {"action":"long_press","id":7}
  {"action":"type","id":3,"text":"..."}         replaces a text field's content
  {"action":"enter"}                            keyboard enter / search key
  {"action":"scroll","direction":"down"}        or "up"
  {"action":"back"}  {"action":"home"}
  {"action":"wait","seconds":8}                 loading / image generation (max 20)
  {"action":"find_contact","name":"Ravi"}       look up a phone contact
  {"action":"whatsapp_send_latest_image","contact":"Ravi"}
        opens that contact's WhatsApp chat with the image saved in the last
        15 minutes attached (then tap the "Send" element on the preview)
  {"action":"whatsapp_chat","contact":"Ravi","text":"optional message"}
        opens that contact's WhatsApp chat with the text typed in
  {"action":"skill","command":"torch on karo"}  built-in phone command (call,
        sms, alarm, timer, torch, volume, battery, settings…)
  {"action":"say","text":"..."}                 short progress update in {LANG}
  {"action":"done","summary":"..."}             one line in {LANG} for the user
  {"action":"fail","reason":"..."}              one line in {LANG} for the user

Rules:
- One action per turn. After each action, check the new screen to verify it
  worked before moving on. Never assume.
- If the screen is the AERIS app itself, open the app you need.
- AI apps (Gemini, ChatGPT…): type the prompt into the message box, e.g.
  "Generate an image of a person standing in a kitchen", tap the send
  button, then wait 8-15 s and re-check until the image appears. If it is
  still generating, wait again.
- Getting an image out: prefer a Download / Save button on the image, or
  long_press the image and pick Download / Save image; then use
  whatsapp_send_latest_image. Fallback: the image's Share button → WhatsApp
  → search the contact → select → tap the send arrow.
- Only send messages to the recipient in the GOAL. Never pay, buy,
  subscribe or upgrade, never delete anything, never change passwords.
- Dismiss pop-ups / tips that block you (Close, Not now, Skip, Got it).
- If an action fails or nothing changes, try a different way (another
  element, scroll, back). After several dead ends, fail with the reason.
- Say done only after the screen confirms the goal is complete.
''';

  /// Messaging apps where a "Send" tap reaches another person.
  static const _messagingApps = {
    'com.whatsapp',
    'com.whatsapp.w4b',
    'org.telegram.messenger',
    'com.google.android.apps.messaging',
    'com.google.android.gm',
    'com.instagram.android',
    'com.facebook.orca',
  };
  static final _sendLabel = RegExp(r'\bsend\b|bhej|भेज', caseSensitive: false);
  static final _moneyLabel = RegExp(
      r'\b(pay|payment|buy|purchase|place order|subscribe|upgrade|'
      r'uninstall|delete account)\b',
      caseSensitive: false);

  /// Carry out [goal] under the confirmed [plan]. [onProgress] gets each
  /// step's thought (for the HUD), [say] speaks progress, [cancelled] is
  /// polled before every step.
  Future<AgentResult> run(String goal, AgentPlan plan,
      {void Function(String)? onProgress,
      Future<void> Function(String)? say,
      bool Function()? cancelled}) async {
    final started = DateTime.now();
    final history = <String>[];
    final seen = <String, int>{}; // action+screen signature → repeats
    var brainErrors = 0;
    for (var step = 1; step <= maxSteps; step++) {
      if (cancelled?.call() == true) {
        return AgentResult(
            false, Lang.t('Theek hai, kaam rok diya.', 'Okay, I stopped.'),
            step - 1);
      }
      if (DateTime.now().difference(started) > timeLimit) {
        return AgentResult(
            false,
            Lang.t('Bahut der lag rahi thi, isliye ruk gaya.',
                'This was taking too long, so I stopped.'),
            step - 1);
      }
      final screen = await device.screen();
      final prompt = _stepPrompt(goal, plan, history, screen, step);
      Map<String, dynamic> act;
      try {
        act = await brain(_lang(_stepSystem), prompt);
      } catch (e) {
        AerisLog.add('agent', 'step $step brain error: $e');
        if (++brainErrors >= 3) {
          return AgentResult(
              false,
              Lang.t('Cloud brain se baat nahi ho pa rahi, isliye ruk gaya.',
                  'I can\'t reach the cloud brain, so I stopped.'),
              step);
        }
        await device.wait(const Duration(seconds: 2));
        continue;
      }
      final action = (act['action'] ?? '').toString();
      final thought = (act['thought'] ?? '').toString();
      if (thought.isNotEmpty) onProgress?.call(thought);

      if (action == 'done') {
        final s = (act['summary'] ?? '').toString().trim();
        return AgentResult(true, s.isEmpty ? Lang.t('Ho gaya.', 'Done.') : s, step);
      }
      if (action == 'fail') {
        final r = (act['reason'] ?? '').toString().trim();
        return AgentResult(
            false, r.isEmpty ? Lang.t('Ye kaam nahi ho paya.', 'I couldn\'t finish that.') : r, step);
      }

      final result = await _execute(act, screen, plan, say);
      final line = '$step. ${describe(act, screen)} → $result';
      AerisLog.add('agent', line);
      history.add(line);

      final sig = '$action|${act['id']}|${act['text']}|${screen.hashCode}';
      final n = seen[sig] = (seen[sig] ?? 0) + 1;
      if (n >= 3) {
        history.add('NOTE: you repeated the same action on the same screen '
            '$n times without progress — do something different.');
      }
      if (_uiActions.contains(action)) await device.wait(settle);
    }
    return AgentResult(false,
        Lang.t('Itne steps mein kaam poora nahi hua, isliye ruk gaya.',
            'I couldn\'t finish within the step limit, so I stopped.'),
        maxSteps);
  }

  static const _uiActions = {
    'open_app', 'tap', 'long_press', 'type', 'enter', 'scroll', 'back',
    'home', 'whatsapp_send_latest_image', 'whatsapp_chat', 'skill',
  };

  static String _stepPrompt(String goal, AgentPlan plan, List<String> history,
      String screen, int step) {
    final recent =
        history.length > 15 ? history.sublist(history.length - 15) : history;
    final plan_ = [
      for (var i = 0; i < plan.steps.length; i++) '${i + 1}. ${plan.steps[i]}'
    ].join('\n');
    return 'GOAL: $goal\n\nPLAN:\n$plan_\n\n'
        'HISTORY:\n${recent.isEmpty ? '(nothing yet)' : recent.join('\n')}\n\n'
        'CURRENT SCREEN (step $step):\n'
        '${screen.isEmpty ? '(unreadable — screen locked, or screen control is off)' : screen}\n\n'
        'Reply with ONE JSON action.';
  }

  /// The `"label"` of element [id] in a dumpUi() [screen], or ''.
  static String labelFor(String screen, int id) {
    final m = RegExp('^\\[$id\\] \\S+ "([^"]*)"', multiLine: true)
        .firstMatch(screen);
    return m?.group(1) ?? '';
  }

  /// Package name from a dumpUi() [screen]'s first line.
  static String appOf(String screen) {
    final m = RegExp(r'^app: (\S+)').firstMatch(screen);
    return m?.group(1) ?? '';
  }

  /// Human-readable one-liner of an action, for HISTORY and the log.
  static String describe(Map<String, dynamic> act, String screen) {
    final a = act['action'];
    final id = _int(act['id']);
    final label = id == null ? '' : ' "${labelFor(screen, id)}"';
    switch (a) {
      case 'tap':
      case 'long_press':
        return '$a [$id]$label';
      case 'type':
        return 'type "${act['text']}" into [${id ?? 'focused'}]$label';
      case 'open_app':
        return 'open_app ${act['app']}';
      case 'wait':
        return 'wait ${act['seconds']}s';
      case 'scroll':
        return 'scroll ${act['direction'] ?? 'down'}';
      case 'find_contact':
      case 'whatsapp_send_latest_image':
        return '$a ${act['name'] ?? act['contact']}';
      case 'whatsapp_chat':
        return 'whatsapp_chat ${act['contact']} "${act['text'] ?? ''}"';
      case 'skill':
        return 'skill "${act['command']}"';
      case 'say':
        return 'say "${act['text']}"';
      default:
        return '$a';
    }
  }

  static int? _int(Object? v) =>
      v is int ? v : (v is num ? v.toInt() : int.tryParse('${v ?? ''}'));

  /// Run one action; returns a short result string for HISTORY.
  Future<String> _execute(Map<String, dynamic> act, String screen,
      AgentPlan plan, Future<void> Function(String)? say) async {
    String ok(bool b) => b ? 'ok' : 'FAILED';
    final id = _int(act['id']);
    switch (act['action']) {
      case 'open_app':
        final app = (act['app'] ?? '').toString();
        return await device.openApp(app) ? 'opened' : 'FAILED: "$app" not installed';
      case 'tap':
        if (id == null) return 'FAILED: tap needs an id';
        final label = labelFor(screen, id);
        if (_moneyLabel.hasMatch(label)) {
          return 'BLOCKED: AERIS never taps payment/purchase/delete buttons';
        }
        if (!plan.messagesSomeone &&
            _messagingApps.contains(appOf(screen)) &&
            _sendLabel.hasMatch(label)) {
          return 'BLOCKED: the user did not approve sending a message';
        }
        return ok(await device.tap(id));
      case 'long_press':
        if (id == null) return 'FAILED: long_press needs an id';
        return ok(await device.longPress(id));
      case 'type':
        return ok(await device.type(id ?? -1, (act['text'] ?? '').toString()));
      case 'enter':
        return ok(await device.enter());
      case 'scroll':
        return ok(await device.scroll(act['direction'] != 'up'));
      case 'back':
      case 'home':
        return ok(await device.global(act['action'] as String));
      case 'wait':
        final secs = (_int(act['seconds']) ?? 5).clamp(1, 20);
        await device.wait(Duration(seconds: secs));
        return 'waited ${secs}s';
      case 'find_contact':
        final hits = await device.contacts((act['name'] ?? '').toString());
        if (hits.isEmpty) return 'no contact found';
        return hits.map((h) => '${h.$1} (+${h.$2})').join(', ');
      case 'whatsapp_send_latest_image':
        if (!plan.messagesSomeone) {
          return 'BLOCKED: the user did not approve sending a message';
        }
        final c = await _contact(act['contact'] ?? act['name']);
        if (c == null) return 'FAILED: contact not found';
        final err = await device.whatsappLatestImage(c.$2);
        return err.isEmpty
            ? 'opened ${c.$1}\'s WhatsApp chat with the image attached — '
                'now tap Send'
            : 'FAILED: $err';
      case 'whatsapp_chat':
        if (!plan.messagesSomeone) {
          return 'BLOCKED: the user did not approve sending a message';
        }
        final c = await _contact(act['contact'] ?? act['name']);
        if (c == null) return 'FAILED: contact not found';
        return await device.whatsappChat(c.$2, (act['text'] ?? '').toString())
            ? 'opened ${c.$1}\'s WhatsApp chat'
            : 'FAILED: could not open WhatsApp';
      case 'skill':
        final r = await device.skill((act['command'] ?? '').toString());
        return r ?? 'FAILED: not a built-in phone command';
      case 'say':
        final t = (act['text'] ?? '').toString();
        if (t.isNotEmpty) await say?.call(t);
        return 'said';
      default:
        return 'FAILED: unknown action "${act['action']}"';
    }
  }

  Future<(String, String)?> _contact(Object? name) async {
    final hits = await device.contacts('${name ?? ''}');
    return hits.isEmpty ? null : hits.first;
  }
}

/// The real phone: accessibility service + platform channels.
class AndroidAgentDevice implements AgentDevice {
  @override
  Future<String> screen() => AccessibilityBridge.dumpUi();
  @override
  Future<bool> tap(int id) => AccessibilityBridge.clickId(id);
  @override
  Future<bool> longPress(int id) => AccessibilityBridge.longClickId(id);
  @override
  Future<bool> type(int id, String text) =>
      AccessibilityBridge.typeId(id, text);
  @override
  Future<bool> enter() => AccessibilityBridge.pressEnter();
  @override
  Future<bool> scroll(bool forward) =>
      AccessibilityBridge.scroll(forward: forward);
  @override
  Future<bool> global(String which) => AccessibilityBridge.global(which);
  @override
  Future<bool> openApp(String name) => AppLauncher.launch(name);
  @override
  Future<List<String>> apps() => AppLauncher.installed();
  @override
  Future<List<(String, String)>> contacts(String name) =>
      PhoneSkills.findContacts(name);

  @override
  Future<String> whatsappLatestImage(String phone) async {
    // Android 13+: READ_MEDIA_IMAGES (photos); older: storage.
    if (!await Permission.photos.request().isGranted &&
        !await Permission.storage.request().isGranted) {
      return 'photo permission denied';
    }
    return AppLauncher.whatsappLatestImage(phone);
  }

  @override
  Future<bool> whatsappChat(String phone, String text) => launchUrl(
      Uri.parse('https://wa.me/$phone?text=${Uri.encodeComponent(text)}'),
      mode: LaunchMode.externalApplication);

  @override
  Future<String?> skill(String command) async =>
      (await PhoneSkills.handle(command))?.spoken;

  @override
  Future<void> wait(Duration d) => Future.delayed(d);
}
