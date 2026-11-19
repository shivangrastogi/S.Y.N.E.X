import '../core/models.dart';
import 'memory_search.dart';
import 'parse.dart';

/// What AERIS decided to do with an utterance. Pure data.
class Plan {
  const Plan(this.tool, [this.args = const {}, this.needsApproval = false]);
  final String tool;
  final Map<String, Object?> args;
  final bool needsApproval;

  Plan withArgs(Map<String, Object?> more) => Plan(tool, {...args, ...more}, needsApproval);

  @override
  String toString() => 'Plan($tool, $args${needsApproval ? ', approval' : ''})';
}

/// Known apps → Android package (or a system action, prefixed `action:`).
const knownApps = <String, String>{
  'whatsapp': 'com.whatsapp',
  'google': 'com.google.android.googlequicksearchbox',
  'youtube': 'com.google.android.youtube',
  'instagram': 'com.instagram.android',
  'insta': 'com.instagram.android',
  'chrome': 'com.android.chrome',
  'maps': 'com.google.android.apps.maps',
  'google maps': 'com.google.android.apps.maps',
  'gmail': 'com.google.android.gm',
  'spotify': 'com.spotify.music',
  'telegram': 'org.telegram.messenger',
  'play store': 'com.android.vending',
  'photos': 'com.google.android.apps.photos',
  'gallery': 'com.google.android.apps.photos',
  'gemini': 'com.google.android.apps.bard',
  'chatgpt': 'com.openai.chatgpt',
  'chat gpt': 'com.openai.chatgpt',
  'linkedin': 'com.linkedin.android',
  'netflix': 'com.netflix.mediaclient',
  'amazon': 'in.amazon.mShop.android.shopping',
  'flipkart': 'com.flipkart.android',
  'paytm': 'net.one97.paytm',
  'phonepe': 'com.phonepe.app',
  'phone pe': 'com.phonepe.app',
  'gpay': 'com.google.android.apps.nbu.paisa.user',
  'google pay': 'com.google.android.apps.nbu.paisa.user',
  'swiggy': 'in.swiggy.android',
  'zomato': 'com.application.zomato',
  'uber': 'com.ubercab',
  'ola': 'com.olacabs.customer',
  'twitter': 'com.twitter.android',
  'facebook': 'com.facebook.katana',
  'snapchat': 'com.snapchat.android',
  'calendar': 'com.google.android.calendar',
  'drive': 'com.google.android.apps.docs',
  'camera': 'action:android.media.action.STILL_IMAGE_CAMERA',
  'settings': 'action:android.settings.SETTINGS',
  'setting': 'action:android.settings.SETTINGS',
  'clock': 'action:android.intent.action.SHOW_ALARMS',
  'alarms': 'action:android.intent.action.SHOW_ALARMS',
  'dialer': 'action:android.intent.action.DIAL',
  'phone': 'action:android.intent.action.DIAL',
  'wifi': 'action:android.settings.WIFI_SETTINGS',
  'wifi settings': 'action:android.settings.WIFI_SETTINGS',
  'bluetooth': 'action:android.settings.BLUETOOTH_SETTINGS',
};

const _enders = ['bas', 'bass', 'bye', 'bye bye', 'ruk jao', 'stop', 'band karo', 'khatam', 'thats all', 'that is all', 'bas karo', 'bas itna hi', 'ok bye', 'chalo bye'];
const _yes = ['haan', 'ha', 'haa', 'han', 'haanji', 'haan ji', 'ji haan', 'yes', 'yeah', 'yep', 'ok', 'okay', 'theek hai', 'thik hai', 'sure', 'bhejo', 'bhej do', 'send', 'send it', 'kar do', 'karo', 'go ahead', 'do it', 'search karo', 'chalega', 'bilkul', 'zaroor', 'jaroor', 'sahi hai', 'done'];
// No bare "na" here: it is handled by position in [yesNo] ("haan na" = yes).
const _no = ['nahi', 'nahin', 'no', 'nope', 'mat', 'mat bhejo', 'mat karo', 'cancel', 'rehne do', 'rahne do', 'ruko', 'dont', 'do not', 'not now', 'cancel karo'];

/// Every word a pure "yes" reply may contain. A reply with any other word
/// ("papa ko call karo") is a new command, not an answer — even though it
/// contains "karo" (review, 2026-11-17: it used to approve the pending message).
const _yesReplyWords = {
  'haan', 'ha', 'haa', 'han', 'haanji', 'ji', 'yes', 'yeah', 'yep', 'ok', 'okay', 'theek', 'thik', 'hai',
  'sure', 'bhejo', 'bhej', 'do', 'de', 'dijiye', 'send', 'it', 'kar', 'karo', 'kijiye', 'karna', 'go',
  'ahead', 'search', 'chalega', 'bilkul', 'zaroor', 'jaroor', 'sahi', 'done', 'please', 'plz', 'na',
  'naa', 'yaar', 'bhai', 'abhi', 'jaldi', 'chalo', 'aeris', 'perfect', 'right', 'correct', 'its', 'fine',
  'ye', 'yeh', 'isko', 'wahi', 'haa ji', 'aage', 'badho', 'google', 'pe', 'par', 'dhoondo', 'dekho',
};

enum YesNo { yes, no, neither }

/// The answer to an approval question ("Ravi ko ye bhejun?").
///
/// Hinglish rules that matter here:
///  - a trailing "na" is a softener — "haan bhej do na" means YES;
///  - "na" counts as no only when it leads ("na, rehne do") or stands alone;
///  - "mat bhejo" contains "bhejo", so a no-word always wins;
///  - a yes must be a *pure* reply — other words make it a new command.
YesNo yesNo(String raw) {
  final s = normalize(raw);
  if (s.isEmpty) return YesNo.neither;
  final words = s.split(' ');
  if (words.first == 'na' || words.first == 'naa') return YesNo.no;
  if (hasAny(s, _no)) return YesNo.no;
  if (hasAny(s, _yes) && words.every(_yesReplyWords.contains)) return YesNo.yes;
  return YesNo.neither;
}

/// Words that may sit around a protocol phrase without changing its meaning:
/// "focus mode on karo", "start focus mode", "good morning AERIS".
const _protocolFiller = {
  'on', 'karo', 'kar', 'do', 'chalu', 'start', 'shuru', 'activate', 'lagao', 'laga', 'please', 'plz', 'aeris',
  'hey', 'hi', 'ok', 'okay', 'ji', 'bhai', 'dost', 'turn', 'enable', 'the', 'mode', 'kijiye', 'dijiye', 'zara',
};

/// True when [s] asks for the protocol whose phrase is [phrase] — the phrase
/// plus only filler words. "focus mode band karo" and "good morning message
/// mummy ko bhejo" are NOT the protocol (review, 2026-11-17: substring match
/// used to run them).
bool protocolAsked(String s, String phrase) {
  if (phrase.isEmpty) return false;
  if (s == phrase) return true;
  final at = RegExp('(^|\\s)${RegExp.escape(phrase)}(\\s|\$)').firstMatch(s);
  if (at == null) return false;
  final rest = '${s.substring(0, at.start)} ${s.substring(at.end)}'.trim();
  if (rest.isEmpty) return true;
  return rest.split(RegExp(r'\s+')).every(_protocolFiller.contains);
}

/// Turns one utterance into a [Plan]. Deterministic, offline, ~µs.
/// Order matters: specific intents before generic ones (one owner per phrase).
class Router {
  const Router();

  Plan route(String raw, {List<Protocol> protocols = const [], List<Memory> memories = const [], DateTime? now}) {
    final s = normalize(raw);
    final t = now ?? DateTime.now();
    if (s.isEmpty) return const Plan('unknown');

    // 1 — end the conversation
    if (_enders.contains(s) || RegExp(r'^(ok |okay |theek hai )?(bas|bye)( karo| bye)?$').hasMatch(s)) {
      return const Plan('end');
    }

    // 2 — protocols ("one phrase, many actions")
    for (final p in protocols) {
      if (!p.enabled) continue;
      if (protocolAsked(s, normalize(p.phrase))) {
        return Plan('protocol', {'id': p.id, 'name': p.name});
      }
    }

    // 3 — message (WhatsApp / SMS), before anything a message's text could
    // mention ("Ravi ko message karo ki volume kam kar de"). Needs approval.
    final message = _messageFor(s);
    if (message != null) return message;

    // 3b — reminders, before "remember": "kal 9 baje yaad dilana ki dawai leni
    // hai", "remind me to call mom at 5", "10 minute baad batana". The phone's
    // Clock app rings them: an alarm (or timer) labelled with what to remember.
    if (_reminderAsked(s, t)) return _reminder(s, t);

    // 4 — remember. Matched on the normalized text, but the note is taken
    // from what the user actually said, so "car B2" stays "B2".
    RegExpMatch? x;
    final lead = RegExp(r'^(?:please )?(?:yaad rakh(?:o|na|iye|lo)?|yaad kar lo|remember|note (?:karo|kar lo|down|this)?)\s*(?:ki|that|ke)?\s+(.+)$', caseSensitive: false);
    final tail = RegExp(r'^(.+?)\s+(?:ye |yeh )?yaad (?:rakh(?:o|na|iye|lo)?|kar lo)$', caseSensitive: false);
    final rawClean = raw.trim().replaceAll(RegExp(r'[.!?]+$'), '').replaceAll(RegExp(r'\s+'), ' ');
    for (final re in [lead, tail]) {
      if ((x = re.firstMatch(s)) != null) {
        final original = re.firstMatch(rawClean);
        return Plan('remember', {'text': _clean(original?[1] ?? x![1]!)});
      }
    }

    // 5 — timer ("timer band karo" stops one instead of asking how long)
    if (hasAny(s, ['timer', 'timers', 'countdown'])) {
      if (_cancels(s)) return const Plan('cancel_timer');
      final secs = parseDuration(s);
      if (secs == null) return const Plan('clarify', {'for': 'timer'});
      return Plan('timer', {'seconds': secs});
    }

    // 6 — alarm: cancel one, ask which is set, "in 20 minutes", or a clock time
    if (hasAny(s, ['alarm', 'alarms', 'jaga dena', 'jagana', 'utha dena', 'uthana', 'wake me', 'wake me up'])) {
      if (_cancels(s)) {
        final c = parseClock(s, t);
        return Plan('cancel_alarm', c == null ? const {} : {'hour': c.hour, 'minute': c.minute, 'spoken': c.spoken});
      }
      if (_asksWhichAlarm(s)) return const Plan('next_alarm');
      final secs = _relativeDuration(s);
      if (secs != null) {
        final at = t.add(Duration(seconds: secs));
        final c = Clock(at.hour, at.minute);
        return Plan('alarm', {'hour': c.hour, 'minute': c.minute, 'spoken': c.spoken});
      }
      final c = parseClock(s, t);
      if (c == null) return const Plan('clarify', {'for': 'alarm'});
      return _timed('alarm', c, s, t);
    }

    // 7 — torch. Needs a switch word: "flipkart flash sale search karo" and
    // "torch kharidna hai" are not torch commands (review, 2026-11-17).
    final torchWord = hasAny(s, ['torch', 'flashlight', 'flash light', 'tourch', 'torch light']) ||
        (hasAny(s, ['flash']) && hasAny(s, ['on', 'off', 'jalao', 'jala do', 'band', 'bujhao']));
    if (torchWord && !_looksLikeShopping(s) && (s == 'torch' || s == 'flashlight' || hasAny(s, _switchWords))) {
      final off = hasAny(s, ['off', 'band', 'bujhao', 'bujha do', 'disable', 'turn off', 'switch off', 'band karo', 'hatao']);
      return Plan('torch', {'on': !off});
    }

    // 8 — phone controls: ringer, volume, what's playing, quick settings.
    // Before "call": "phone silent karo" used to call a contact named "silent".
    final device = _deviceControl(s);
    if (device != null) return device;

    // 10 — call ("phone ki battery" is not a call; bare "call karo" asks who)
    if (RegExp(r'^(call|phone) (karo|lagao|kar do)$').hasMatch(s) || s == 'call') {
      return const Plan('clarify', {'for': 'call'});
    }
    if (!RegExp(r'\b(phone|mobile) (ki|ka|ke)\b').hasMatch(s) &&
        ((x = RegExp(r'^(?:call|phone|dial|ring)\s+(?:to\s+)?(.+?)(?:\s+(?:karo|kar do|lagao|milao))?$').firstMatch(s)) != null ||
            (x = RegExp(r'^(.+?)\s+(?:ko|pe|par)\s+(?:call|phone|fone|dial)(?:\s+(?:karo|kar do|lagao|laga do|milao|kar))?$').firstMatch(s)) != null)) {
      final who = _clean(x![1]!);
      if (who.isEmpty) return const Plan('clarify', {'for': 'call'});
      // "phone restart karo", "ring tone change karo" are about the phone, not a person
      if (!_notAPerson(who) && !_aboutThePhone.hasMatch(who)) return Plan('call', {'to': who});
    }

    // 11 — open an app (before search: "open google" is an app)
    if ((x = RegExp(r'^(?:open|launch|start)\s+(.+)$').firstMatch(s)) != null ||
        (x = RegExp(r'^(.+?)\s+(?:kholo|khol do|open karo|open kar do|chalu karo|start karo|launch karo|open)$').firstMatch(s)) != null) {
      final name = _clean(x![1]!).replaceAll(RegExp(r'\s+(app|application)$'), '');
      if (_justMusic.hasMatch(name)) return const Plan('play', {'q': ''}); // "music chalu karo"
      final pkg = knownApps[name];
      if (pkg != null) return Plan('open', {'app': name, 'target': pkg});
      return Plan('open', {'app': name, 'target': null}); // looked up among installed apps
    }

    // 12 — play music ("arijit singh ke gaane bajao", "play believer on spotify")
    final play = _playRequest(s);
    if (play != null) return play;

    // 13 — directions ("ghar ka rasta dikhao", "navigate to india gate")
    final nav = _navigation(s);
    if (nav != null) return nav;

    // 14 — search the web
    if ((x = RegExp(r'^(?:google|search|search for|look up|google pe search karo|google par search karo)\s+(.+)$').firstMatch(s)) != null ||
        (x = RegExp(r'^(.+?)\s+(?:google|search|search karo|google karo|google pe search karo|google par dhundo|dhundo|dhoondo)$').firstMatch(s)) != null) {
      return Plan('search', {'q': _clean(x![1]!)});
    }

    // 15 — live information: weather, news, scores, "train ka time" (needs
    // the internet, so it asks first). Before "time": "what time is the
    // match" is not asking the clock (review, 2026-11-17).
    if (RegExp(r'\b(mausam|weather|temperature|tapmaan|baarish|barish|rain|forecast|news|khabar|khabren|headlines|score|cricket|match|stock|share price|sensex|nifty|gold rate|sone ka bhav|petrol price|traffic)\b').hasMatch(s) ||
        RegExp(r'\b(?!abhi\b|aaj\b|current\b|india\b|yahan\b)[a-z]+ (?:ka|ki|ke) (?:time|samay|timing|timings)\b').hasMatch(s) ||
        RegExp(r'\bwhat time (?:is|does|do|will|did|are|was|should|shall) (?!it\b)').hasMatch(s)) {
      return Plan('search', {'q': raw.trim(), 'reason': 'live_info'}, true);
    }

    // 16 — battery / time / date
    if (s == 'battery' ||
        RegExp(r'\bbattery\b.*\b(kitni|kitna|level|status|percent|kya|batao|bata|how much|left|hai)\b|\b(how much|kitni|kitna) (battery|charge)\b|\bcharging (hai|ho rahi|status)').hasMatch(s)) {
      return const Plan('battery');
    }
    if (s == 'date' ||
        s == 'today' ||
        RegExp(r'\b(aaj (ki )?(date|tareekh|tarikh)|(date|tareekh|tarikh) (kya|batao|bata|hai)|what(s| is) (the )?(date|day)|todays? date|aaj (kya|kaunsa|konsa) din|(what|which) day is it|which day|kaunsa din hai|aaj ka din)\b').hasMatch(s)) {
      return const Plan('date');
    }
    if (s == 'time' ||
        RegExp(r'\b((kya|what) time|time (kya|batao|bata|kitna|hua|ho gaya|please|hai)|kitne baje|kya baja|kitna baja|samay kya|what(s| is) the time|current time|abhi (ka )?time)\b').hasMatch(s)) {
      return const Plan('time');
    }

    // 17 — maths
    final m = parseMath(s);
    if (m != null) return Plan('math', {'expr': m.expr, 'value': m.value});

    // 18 — recall something remembered
    if (memories.isNotEmpty &&
        // "gate code kya hai" must recall too (phone test, 2026-11-17). Safe:
        // this only answers when the question shares real words with a memory.
        RegExp(r'\b(kahan|kaha|where|kya yaad|what did i|yaad hai|kab|when|kaun|who|kaunsa|which|batao|tell me|kya hai|kya tha|kya thi|kitna hai|what is|whats|what was)\b').hasMatch(s)) {
      final best = bestMatchingMemory(s, memories);
      if (best != null) return Plan('recall', {'id': best.id, 'text': best.text});
    }

    // 19 — small talk
    if (RegExp(r'^(hi|hello|hey|namaste|namaskar|hii|helo|hey aeris|hi aeris|hello aeris|aeris|suno)$').hasMatch(s)) {
      return const Plan('greet');
    }
    if (hasAny(s, ['thank you', 'thanks', 'thank u', 'shukriya', 'dhanyavad', 'dhanyawad', 'thnx'])) {
      return const Plan('thanks');
    }
    // Only a request for help with AERIS itself — "mujhe help chahiye bank
    // account kholne mein" is a real question for the brain (review, 2026-11-17).
    if (RegExp(r'^(help|madad|help me|help karo|madad karo|help please|madad chahiye|help chahiye)$').hasMatch(s) ||
        RegExp(r'(kya kar sakt|kya kya kar|what can you do|what all can you do|how can you help|tumhe kya aata|kya aata hai tumhe)').hasMatch(s)) {
      return const Plan('help');
    }
    if (RegExp(r'(who are you|kaun ho|tum kaun|aap kaun|your name|tumhara naam|aapka naam)').hasMatch(s)) {
      return const Plan('who');
    }
    if (RegExp(r'(how are you|kaise ho|kaisi ho|kya haal|how r u)').hasMatch(s)) return const Plan('howareyou');

    // 20 — nothing matched: offer a web search (asks first)
    return Plan('search', {'q': raw.trim(), 'fallback': true}, true);
  }

  /// "Ravi ko WhatsApp karo ki …", "send a message to mom saying …",
  /// "message bhejo papa ko", "papa ko bolo ki main late aaunga".
  static Plan? _messageFor(String s) {
    final forms = <(RegExp, int, int?, int)>[
      // (pattern, who group, app group (null = SMS), body group)
      (RegExp(r'^(.+?) ko (whatsapp|whats app|message|msg|sms|text|massage)(?: (?:karo|bhejo|kar do|send karo|bhej do|karna))?(?:\s+(?:ki|ke|that|bolo|likho)\s+(.+))?$'), 1, 2, 3),
      (RegExp(r'^(?:send |bhejo )?(?:a )?(whatsapp|whats app|message|msg|sms|text)(?: message)? to (.+?)(?:\s+(?:saying|that|ki)\s+(.+))?$'), 2, 1, 3),
      // "ek" is already "1" after normalize
      (RegExp(r'^(?:1 |ek |a )?(whatsapp|whats app|message|msg|sms|text)(?: message)? (?:bhejo|bhej do|karo|kar do|send karo|send) (.+?) ko(?:\s+(?:ki|ke|that)\s+(.+))?$'), 2, 1, 3),
      // telling someone something is a message
      (RegExp(r'^(.+?) ko (?:bolo|bol do|bata do|batao|keh do|kehna|kaho|bolna|bata dena|inform karo) (?:ki |ke |that )?(.+)$'), 1, null, 2),
    ];
    for (final (re, whoGroup, appGroup, bodyGroup) in forms) {
      final x = re.firstMatch(s);
      if (x == null) continue;
      final who = x[whoGroup]!;
      if (_notAPerson(who) || RegExp(r'\b(yaad|remind\w*|remember|alarm|timer)\b').hasMatch(who)) continue;
      return _message(who, appGroup == null ? 'sms' : x[appGroup]!, x[bodyGroup]);
    }
    return null;
  }

  static Plan _message(String who, String app, String? body) {
    final isWa = app.startsWith('wha');
    final to = _clean(who);
    final b = body == null ? null : _clean(body);
    if (b == null || b.isEmpty) {
      return Plan('clarify', {'for': 'message', 'to': to, 'app': isWa ? 'whatsapp' : 'sms'});
    }
    return Plan('message', {'to': to, 'body': b, 'app': isWa ? 'whatsapp' : 'sms'}, true);
  }

  static String _clean(String s) => s
      .replaceAll(RegExp(r'^(please|zara|jara|plz|pls)\s+'), '')
      .replaceAll(RegExp(r'\s+(please|plz|pls|na|zara)$'), '')
      .trim();

  // ── alarms, timers, reminders ─────────────────────────────────────

  /// "band karo", "cancel", "hata do", "off" — stop or remove something.
  static bool _cancels(String s) => hasAny(s, [
        'cancel', 'band', 'band karo', 'band kar do', 'hata', 'hatao', 'hata do', 'delete', 'remove', 'stop',
        'off', 'turn off', 'mita', 'mita do', 'mitao', 'dismiss', 'khatam', 'nahi chahiye',
      ]);

  /// "alarm kitne baje ka hai", "next alarm kab hai" — asking, not setting.
  static bool _asksWhichAlarm(String s) =>
      RegExp(r'\b(kitne baje|kab|kaunsa|konsa|kaun sa|kon sa|next|agla|which|when|what time|laga hai|lage hain|lagaya hai|set hai|kya hai|hai kya)\b').hasMatch(s) &&
      !RegExp(r'\b(laga do|lagao|laga dena|set karo|set kar do|set an?|set for|set my|jaga dena|utha dena|wake me)\b').hasMatch(s);

  /// A length after "in / baad / mein / for": "alarm for 5 minutes",
  /// "20 minute baad jaga dena". Null when the sentence names a clock time.
  static int? _relativeDuration(String s) {
    if (!RegExp(r'\b(in|after|baad|mein|me|for|later)\b').hasMatch(s)) return null;
    return parseDuration(s);
  }

  /// "kal subah 8 baje" said at 7 am: Android's Clock app takes only a time,
  /// so this alarm would ring TODAY at 8. Flag it and ask first.
  static bool _tomorrowClash(Clock c, String s, DateTime now) =>
      hasAny(s, ['kal', 'tomorrow']) && now.hour >= 4 && c.hour * 60 + c.minute > now.hour * 60 + now.minute;

  static Plan _timed(String tool, Clock c, String s, DateTime now, [Map<String, Object?> extra = const {}]) {
    final clash = _tomorrowClash(c, s, now);
    return Plan(tool, {'hour': c.hour, 'minute': c.minute, 'spoken': c.spoken, ...extra, if (clash) 'tomorrowClash': true}, clash);
  }

  static final _remindVerb = RegExp(r'\b(yaad dila\w*|remind\w*)\b');

  static bool _reminderAsked(String s, DateTime now) =>
      _remindVerb.hasMatch(s) ||
      RegExp(r'\b(baad|later)\b.*\b(batana|bata dena)\b').hasMatch(s) ||
      // "remember to buy milk at 6" is a reminder; without a time it's a note
      (RegExp(r'^remember to\b').hasMatch(s) && (parseClock(s, now) != null || _relativeDuration(s) != null));

  static Plan _reminder(String s, DateTime now) {
    final what = reminderText(s);
    final secs = _relativeDuration(s);
    if (secs != null) return Plan('remind', {'seconds': secs, 'text': what});
    final c = parseClock(s, now);
    if (c == null) return Plan('clarify', {'for': 'remind', 'text': what});
    return _timed('remind', c, s, now, {'text': what});
  }

  /// What to be reminded about, without the "when": "kal 9 baje yaad dilana
  /// ki dawai leni hai" → "dawai leni hai"; "remind me to call mom at 5" →
  /// "call mom".
  static String reminderText(String s) {
    final after = RegExp(r'(?:yaad dila\w*|remind\w*(?: me)?|batana|bata dena|remember)\s+(?:ki|ke|to|that|about)\s+(.+)$').firstMatch(s);
    var text = after != null ? after[1]! : s.replaceAll(RegExp(r'\b(yaad dila\w*|remind\w*|batana|bata dena|remember to)\b.*$'), '');
    text = text
        .replaceAll(RegExp(r'\b(?:at|pe|par|ko)?\s*\d{1,2}(?:[:.]\d{2})?\s*(?:baje|bje|am|pm|a m|p m|o ?clock)\b'), ' ')
        .replaceAll(RegExp(r'\b(?:in |after )?\d+(?:\.\d+)?\s*(?:hours?|hrs?|ghante|ghanta|minutes?|mins?|minat|seconds?|secs?)\b(?:\s+(?:baad|mein|me|later))?'), ' ')
        .replaceAll(RegExp(r'\b(?:at|pe|par)\s+\d{1,2}(?:[:.]\d{2})?\b'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
    // "when" words left at either edge: "kal subah dawai lene ka" → "dawai lene"
    const edge = {
      'kal', 'aaj', 'parso', 'tomorrow', 'today', 'subah', 'savere', 'shaam', 'sham', 'raat', 'dopahar', 'morning',
      'evening', 'night', 'tonight', 'mujhe', 'me', 'please', 'zara', 'baad', 'mein', 'ki', 'ke', 'ka', 'to', 'that',
      'ko', 'the', 'at', 'pe', 'par', 'yaad', 'in', 'aadha', 'ghanta', 'dedh',
    };
    final words = text.split(' ').where((w) => w.isNotEmpty).toList();
    while (words.isNotEmpty && edge.contains(words.first)) {
      words.removeAt(0);
    }
    while (words.isNotEmpty && edge.contains(words.last)) {
      words.removeLast();
    }
    return words.join(' ');
  }

  // ── phone controls ────────────────────────────────────────────────

  static const _switchWords = [
    'on', 'off', 'jalao', 'jala do', 'jala', 'jalaao', 'chalu', 'band', 'bujhao', 'bujha do', 'bujha', 'enable',
    'disable', 'turn', 'switch', 'start', 'hatao', 'karo', 'kar do', 'light', 'chalao',
  ];

  /// Buying or looking something up — never a device command.
  static bool _looksLikeShopping(String s) =>
      RegExp(r'\b(search|google|dhundo|dhoondo|look up|price|kharid\w*|buy|order|sale)\b').hasMatch(s);

  /// Words that make "phone X" / "call X" about the phone itself.
  static final _aboutThePhone = RegExp(
      r'\b(silent|vibrate|tone|ringtone|volume|restart|reboot|switch off|band|off|on|lock|unlock|charge|charging|battery|mute|unmute|dnd|storage|update|hang|slow|garam|heat|setting|settings|kharab|reset|format|kitna|kitni|kaisa|kab|kya)\b');

  static const _notPeople = {
    'mujhe', 'mereko', 'mere ko', 'hume', 'humein', 'hamein', 'tum', 'tumhe', 'aap', 'aapko', 'isko', 'usko', 'sabko',
    'aeris', 'me', 'myself',
  };
  static bool _notAPerson(String who) => _notPeople.contains(who.trim());

  static final _justMusic = RegExp(r'^(music|gaana|gana|gaane|gane|song|songs|koi gaana|1 gaana)$');

  static Plan? _deviceControl(String s) {
    if (_looksLikeShopping(s)) return null;
    final off = hasAny(s, ['off', 'band', 'hatao', 'hata do', 'hata', 'disable', 'turn off', 'switch off', 'band karo', 'band kar do', 'nikalo']);

    // ringer: silent / vibrate / normal
    if (RegExp(r'\b(silent|dnd|do not disturb)\b').hasMatch(s)) return Plan('ringer', {'mode': off ? 'normal' : 'silent'});
    if (RegExp(r'\b(vibrate|vibration|vibrate mode)\b').hasMatch(s)) return Plan('ringer', {'mode': off ? 'normal' : 'vibrate'});
    if (RegExp(r'\b(ringer|ring mode|general mode|normal mode)\b').hasMatch(s)) return Plan('ringer', {'mode': off ? 'silent' : 'normal'});

    // volume
    if (RegExp(r'\b(volume|awaaz|aawaz|awaz|awaj|aavaz|sound)\b').hasMatch(s)) {
      final String? action;
      if (RegExp(r'\b(full|max|maximum|poori|puri|sabse tez)\b').hasMatch(s)) {
        action = 'max';
      } else if (RegExp(r'\bunmute\b').hasMatch(s)) {
        action = 'unmute';
      } else if (RegExp(r'\b(mute|band|off)\b').hasMatch(s)) {
        action = 'mute';
      } else if (RegExp(r'\b(kam|ghatao|ghata do|ghata|dheere|dheema|decrease|down|low|lower|neeche|halki)\b').hasMatch(s)) {
        action = 'down';
      } else if (RegExp(r'\b(badhao|badha do|badhaao|badha|tez|increase|up|zyada|jyada|louder|high|upar)\b').hasMatch(s)) {
        action = 'up';
      } else {
        action = null;
      }
      if (action != null) return Plan('volume', {'action': action});
      final level = RegExp(r'\b(\d{1,3})\b').firstMatch(s);
      if (level != null) return Plan('volume', {'action': 'set', 'level': int.parse(level[1]!).clamp(0, 100)});
      return null;
    }

    // what's playing: pause / resume / next / previous
    final aboutMusic = RegExp(r'\b(gaana|gana|gaane|gane|song|songs|music|track|podcast)\b').hasMatch(s);
    final bare = RegExp(r'^(play|pause|resume|next|previous|skip)( it| karo| kar do| song| track)?$').firstMatch(s);
    if (aboutMusic || bare != null) {
      if (RegExp(r'\b(next|agla|agle|skip|change|badlo|dusra|doosra)\b').hasMatch(s)) return const Plan('media', {'action': 'next'});
      if (RegExp(r'\b(previous|pichla|pichhla|pehle wala|last|wapas wala)\b').hasMatch(s)) return const Plan('media', {'action': 'previous'});
      if (RegExp(r'\b(pause|ruko|rok do|roko|band|stop|off)\b').hasMatch(s)) return const Plan('media', {'action': 'pause'});
      if (RegExp(r'\b(resume|continue|phir se|dobara)\b').hasMatch(s) || bare?[1] == 'play') {
        return const Plan('media', {'action': 'play'});
      }
    }

    // quick settings Android won't let an app flip — AERIS opens the panel
    final setting = RegExp(r'\b(wifi|wi fi|bluetooth|hotspot|airplane mode|aeroplane mode|flight mode|location|gps|mobile data|internet|data)\b').firstMatch(s);
    if (setting != null &&
        (off || hasAny(s, ['on', 'chalu', 'chalu karo', 'enable', 'turn on', 'switch on', 'start', 'connect', 'jalao', 'laga do']))) {
      final which = switch (setting[1]!) {
        'wifi' || 'wi fi' => 'wifi',
        'bluetooth' => 'bluetooth',
        'hotspot' => 'hotspot',
        'location' || 'gps' => 'location',
        'mobile data' || 'internet' || 'data' => 'mobile_data',
        _ => 'airplane_mode',
      };
      return Plan('setting', {'which': which, 'on': !off});
    }
    return null;
  }

  // ── music and maps ────────────────────────────────────────────────

  static Plan? _playRequest(String s) {
    RegExpMatch? x;
    String? q;
    if ((x = RegExp(r'^play\s+(.+)$').firstMatch(s)) != null) {
      q = x![1];
    } else if ((x = RegExp(r'^(.+?)\s+(?:bajao|baja do|bajaao|baja de|play karo|play kar do|play)$').firstMatch(s)) != null) {
      q = x![1];
    } else if ((x = RegExp(r'^(.+?)\s+(?:chalao|chala do|laga do|lagao|sunao|suna do)$').firstMatch(s)) != null &&
        RegExp(r'\b(gaana|gana|gaane|gane|song|songs|music|bhajan|ghazal|podcast|playlist|album)\b').hasMatch(x![1]!)) {
      q = x[1];
    }
    if (q == null || q == 'store') return null; // "play store" is an app
    String? app;
    String appOf(String name) => name.contains('music') ? 'youtube_music' : (name.contains('youtube') ? 'youtube' : 'spotify');
    final trailing = RegExp(r'\s+(?:on|pe|par|mein)\s+(youtube music|yt music|youtube|spotify)$').firstMatch(q);
    final leading = RegExp(r'^(youtube music|yt music|youtube|spotify)\s+(?:pe|par|mein|on)\s+').firstMatch(q);
    if (trailing != null) {
      app = appOf(trailing[1]!);
      q = q.substring(0, trailing.start);
    } else if (leading != null) {
      app = appOf(leading[1]!);
      q = q.substring(leading.end);
    }
    q = _clean(q.replaceAll(RegExp(r'^(koi |some |a |an |the |1 |mera |meri |mere )'), ''));
    if (RegExp(r'^(gaana|gana|gaane|gane|song|songs|music|kuch|something|koi bhi gaana|achha gaana|acha gaana)$').hasMatch(q)) q = '';
    return Plan('play', {'q': q, 'app': ?app});
  }

  static Plan? _navigation(String s) {
    RegExpMatch? x;
    String? place;
    final patterns = [
      RegExp(r'^(?:navigate|navigation|directions?|route|rasta|raasta)(?: to| for| tak)?\s+(.+?)(?:\s+(?:dikhao|batao|chahiye))?$'),
      RegExp(r'^(?:take me|le chalo|mujhe le chalo)(?: to)?\s+(.+)$'),
      RegExp(r'^(?:mujhe )?(.+?)\s+(?:tak )?(?:ka|ki|ke)\s+(?:rasta|raasta|route|direction|directions|navigation|map)(?:\s+(?:dikhao|batao|bata do|dikha do|chahiye|kholo|start karo|do|lagao))?$'),
      RegExp(r'^(?:mujhe )?(.+?)\s+(?:kaise|kese)\s+(?:jaun|jau|jaaun|jana hai|jaana hai|jaye|jayen|pahunchu|pahunchun|jaate hain)$'),
      RegExp(r'^(?:mujhe )?(.+?)\s+le chalo$'),
    ];
    for (final re in patterns) {
      if ((x = re.firstMatch(s)) != null) {
        place = x![1];
        break;
      }
    }
    if (place == null) return null;
    place = _clean(place).replaceAll(RegExp(r'\s+(tak|jaane ka|jane ka)$'), '');
    if (place.isEmpty) return null;
    final target = switch (place) {
      'ghar' || 'home' || 'mere ghar' || 'apne ghar' || 'my home' => 'Home',
      'office' || 'daftar' || 'work' || 'mere office' || 'my office' => 'Work',
      _ => place,
    };
    return Plan('navigate', {'place': target});
  }
}
