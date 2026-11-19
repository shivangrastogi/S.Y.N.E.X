import 'package:flutter/foundation.dart';

import '../core/models.dart';
import '../core/store.dart';
import 'parse.dart';
import 'phone.dart';
import 'router.dart';

/// Result of running a plan.
class Outcome {
  const Outcome(this.reply, {this.status = TurnStatus.ok, this.detail});
  final String reply;
  final TurnStatus status;

  /// Optional visible extra (e.g. "12 × 8 = 96"), shown under the reply.
  final String? detail;
}

/// What the approval panel shows.
class Approval {
  const Approval({required this.title, required this.question, this.to, this.body, this.app});
  final String title;
  final String question;
  final String? to;
  final String? body;
  final String? app;
}

class PrepareFailed implements Exception {
  PrepareFailed(this.reply);
  final String reply;
}

/// Several contacts match equally ("Rahul Sharma" and "Rahul Verma"): AERIS
/// asks which one instead of guessing. The answer resolves [plan].
class NeedsChoice implements Exception {
  NeedsChoice(this.plan, this.options, this.question);
  final Plan plan;
  final List<Person> options;
  final String question;
}

/// Runs plans against the phone. Replies follow the language setting
/// (Hinglish default, English modes added alongside — never replacing).
class Executor {
  Executor(this.phone, this.store);
  final Phone phone;
  final Store store;

  bool get _hi => store.settings.lang == Lang.hinglish;
  String t(String hinglish, String english) => _hi ? hinglish : english;
  String get _name => store.settings.name.trim();

  /// Hindi verbs agree with the speaker: male voice → "raha hoon", female → "rahi hoon".
  bool get _male => true; // AERIS's only voice is male (Supertonic voice 9)
  String g(String male, String female) => _male ? male : female;

  /// Resolve who a call or message is for, before acting or asking for
  /// approval. Throws [PrepareFailed] (nobody matches) or [NeedsChoice]
  /// (several people match equally — never dial the wrong Rahul).
  Future<Plan> prepare(Plan p) async {
    if (p.tool != 'message' && p.tool != 'call') return p;
    if (p.args['number'] != null) return p; // already resolved ("which one?" answered)
    final to = '${p.args['to'] ?? ''}'.trim();
    if (to.isEmpty) throw PrepareFailed(t('Kisko? Naam bataiye.', 'Who to? Tell me the name.'));
    if (looksLikeNumber(to)) return p.withArgs({'name': to, 'number': to});
    final found = await phone.findPeople(to);
    if (found.isEmpty) {
      throw PrepareFailed(t('Contacts mein "$to" nahi mila.', 'I couldn\'t find "$to" in your contacts.'));
    }
    final top = topMatches(found, to);
    if (top.length > 1) {
      final options = top.take(3).toList();
      throw NeedsChoice(p, options, choiceQuestion(to, options));
    }
    return p.withArgs({'name': top.first.name, 'number': top.first.number});
  }

  /// "Kaunse Rahul? Rahul Sharma ya Rahul Verma?"
  String choiceQuestion(String said, List<Person> options) {
    final names = options.map((o) => o.name).toList();
    final joined = names.length == 1 ? names.first : '${names.sublist(0, names.length - 1).join(', ')} ${t('ya', 'or')} ${names.last}';
    return t('Kaunse ${_title(said)}? $joined?', 'Which ${_title(said)} — $joined?');
  }

  Approval approval(Plan p) {
    if (p.args['tomorrowClash'] == true) {
      final what = p.tool == 'remind' ? t('reminder', 'reminder') : t('alarm', 'alarm');
      return Approval(
        title: t('Kal ka $what?', 'Tomorrow\'s $what?'),
        question: t('Phone ki Clock app din nahi leti, isliye ye $what aaj hi ${p.args['spoken']} pe baj jaayega. Phir bhi lagaun?',
            'The Clock app can\'t take a date, so this $what would ring today at ${p.args['spoken']}. Set it anyway?'),
        body: '${p.args['spoken']}',
      );
    }
    if (p.tool == 'message') {
      final app = p.args['app'] == 'whatsapp' ? 'WhatsApp' : 'SMS';
      final name = p.args['name'] ?? p.args['to'];
      return Approval(
        title: t('$app pe bhejun?', 'Send on $app?'),
        question: t('$name ko ye bhejun: "${p.args['body']}"?', 'Send this to $name: "${p.args['body']}"?'),
        to: '$name',
        body: '${p.args['body']}',
        app: app,
      );
    }
    if (p.args['reason'] == 'live_info') {
      return Approval(
        title: t('Online dekhun?', 'Look it up online?'),
        question: t('Ye abhi ki jaankari hai, mujhe online dekhna padega. Google pe search karun?',
            "That's live information I'd have to look up. Shall I search Google?"),
        body: '${p.args['q']}',
      );
    }
    // fallback web search
    return Approval(
      title: t('Web pe dhoondun?', 'Search the web?'),
      question: t('Ye mujhe abhi nahi aata. Google pe search karun?', 'I can\'t do that yet. Shall I search Google for it?'),
      body: '${p.args['q']}',
    );
  }

  String clarify(Plan p) => switch (p.args['for']) {
        'alarm' => t('Kis time ka alarm lagaun?', 'What time should I set the alarm for?'),
        'timer' => t('Kitne time ka timer?', 'How long should the timer be?'),
        'call' => t('Kisko call karun?', 'Who should I call?'),
        'message' => t('Kya message bhejun?', 'What should the message say?'),
        'message_to' => t('Kisko bhejun?', 'Who should I send it to?'),
        'remind' => t('Kab yaad dilaun?', 'When should I remind you?'),
        _ => t('Thoda aur batao?', 'Could you say a bit more?'),
      };

  /// How the session turns the answer to a clarify question back into a full
  /// command: `{}` is replaced by what the user said ("6 baje" → "alarm 6 baje").
  String clarifyTemplate(Plan p) {
    final app = p.args['app'] == 'whatsapp' ? 'whatsapp' : 'message';
    final text = '${p.args['text'] ?? ''}'.trim();
    return switch (p.args['for']) {
      'alarm' => 'alarm {}',
      'timer' => 'timer {}',
      'call' => 'call {}',
      'message' => '${p.args['to']} ko $app karo ki {}',
      'message_to' => '{} ko $app karo ki ${p.args['body']}',
      'remind' => text.isEmpty ? '{} yaad dilana' : '{} yaad dilana ki $text',
      _ => '',
    };
  }

  Future<Outcome> run(Plan p) async {
    try {
      return await _run(p);
    } catch (e, stack) {
      // Never read a raw exception aloud ("PlatformException(…)") — log it.
      debugPrint('AERIS ${p.tool} failed: $e\n$stack');
      return Outcome(t('Maaf kijiye, ye abhi nahi ho paaya.', 'Sorry, that didn\'t work just now.'), status: TurnStatus.failed);
    }
  }

  Future<Outcome> _run(Plan p) async {
    final a = p.args;
    switch (p.tool) {
      case 'time':
        final c = Clock(DateTime.now().hour, DateTime.now().minute);
        return Outcome(t('Abhi ${c.spoken} ho rahe hain.', 'It\'s ${c.spoken}.'));

      case 'date':
        final d = DateTime.now();
        final s = '${_days[d.weekday - 1]}, ${d.day} ${_months[d.month - 1]}';
        return Outcome(t('Aaj $s hai.', 'Today is $s.'));

      case 'battery':
        final b = await phone.battery();
        if (b == null) return Outcome(t(g('Battery padh nahi paaya.', 'Battery padh nahi paayi.'), 'I couldn\'t read the battery.'), status: TurnStatus.failed);
        final ch = b.charging ? t(', charging ho rahi hai', ', and charging') : '';
        return Outcome(t('Battery ${b.level}% hai$ch.', 'Battery is at ${b.level}%$ch.'));

      case 'alarm':
        final label = '${a['label'] ?? ''}'.trim();
        await phone.setAlarm(a['hour'] as int, a['minute'] as int, label.isEmpty ? 'AERIS' : _cap(label));
        return Outcome(t('${a['spoken']} ka alarm laga diya.', 'Alarm set for ${a['spoken']}.'));

      case 'remind':
        // The Clock app rings it: a timer or alarm labelled with the reminder.
        final what = '${a['text'] ?? ''}'.trim();
        final label = what.isEmpty ? 'AERIS reminder' : _cap(what);
        final about = what.isEmpty ? '' : ': $what';
        final dilaunga = g('dilaunga', 'dilaungi');
        if (a['seconds'] case final int secs) {
          await phone.setTimer(secs, label);
          return Outcome(t('${speakDuration(secs)} baad yaad $dilaunga$about.', 'I\'ll remind you in ${speakDuration(secs, hinglish: false)}$about.'));
        }
        await phone.setAlarm(a['hour'] as int, a['minute'] as int, label);
        return Outcome(t('${a['spoken']} pe yaad $dilaunga$about.', 'I\'ll remind you at ${a['spoken']}$about.'));

      case 'cancel_alarm':
        if (a['hour'] case final int hour when await phone.dismissAlarm(hour, a['minute'] as int)) {
          return Outcome(t(g('${a['spoken']} wala alarm hata raha hoon.', '${a['spoken']} wala alarm hata rahi hoon.'), 'Removing the ${a['spoken']} alarm.'));
        }
        // No time said (or the Clock app can't search): show the list rather
        // than guess which alarm to switch off.
        await phone.showAlarms();
        return Outcome(t('Alarms khol diye — jo hatana hai use band kar dijiye.', 'Here are your alarms — switch off the one you don\'t need.'));

      case 'cancel_timer':
        // Android lets an app start a timer but not stop one.
        await phone.showTimers();
        return Outcome(t('Timer khol diya — wahan se band kar dijiye.', 'Here\'s your timer — stop it from there.'));

      case 'next_alarm':
        final next = await phone.nextAlarm();
        if (next == null) return Outcome(t('Abhi koi alarm laga nahi hai.', 'No alarm is set.'));
        final at = Clock(next.hour, next.minute).spoken;
        return Outcome(t('Agla alarm ${_dayHi(next)} $at ka hai.', 'Your next alarm is ${_dayEn(next)} at $at.'));

      case 'ringer':
        final mode = a['mode'] as String;
        if (!await phone.setRinger(mode)) {
          await phone.openDndAccess();
          return Outcome(
              t('Iske liye AERIS ko "Do Not Disturb" access chahiye. Setting khol di hai — AERIS ko allow kar dijiye, phir dobara boliye.',
                  'I need Do Not Disturb access for that. I\'ve opened the setting — allow AERIS, then ask again.'),
              status: TurnStatus.failed);
        }
        return Outcome(switch (mode) {
          'silent' => t('Phone silent kar diya.', 'Your phone is on silent.'),
          'vibrate' => t('Phone vibrate pe kar diya.', 'Your phone is on vibrate.'),
          _ => t('Ringer wapas on kar diya.', 'Ringer is back on.'),
        });

      case 'volume':
        final action = a['action'] as String;
        final level = await phone.volume(action, level: a['level'] as int?);
        if (level == null) return Outcome(t(g('Volume badal nahi paaya.', 'Volume badal nahi paayi.'), 'I couldn\'t change the volume.'), status: TurnStatus.failed);
        return Outcome(switch (action) {
          'mute' => t('Awaaz band kar di.', 'Muted.'),
          'max' => t('Volume full kar diya.', 'Volume is at max.'),
          'down' => t('Volume kam kar diya — ab $level%.', 'Volume down — $level% now.'),
          'set' || 'unmute' => t('Volume ab $level% hai.', 'Volume is at $level%.'),
          _ => t('Volume badha diya — ab $level%.', 'Volume up — $level% now.'),
        });

      case 'media':
        final action = a['action'] as String;
        if (action == 'play') return _play('', null);
        await phone.media(action);
        return Outcome(switch (action) {
          'pause' => t('Rok diya.', 'Paused.'),
          'next' => t('Agla gaana.', 'Next track.'),
          'previous' => t('Pichla gaana.', 'Previous track.'),
          _ => t('Theek hai.', 'Done.'),
        });

      case 'play':
        return _play('${a['q'] ?? ''}'.trim(), a['app'] as String?);

      case 'setting':
        final which = a['which'] as String;
        final label = _settingNames[which] ?? _title(which.replaceAll('_', ' '));
        if (!await phone.openSetting(which)) {
          return Outcome(t('$label ki setting nahi khul paayi.', 'I couldn\'t open $label settings.'), status: TurnStatus.failed);
        }
        final on = a['on'] as bool?;
        if (on == null) return Outcome(t('$label settings khol di.', 'Opening $label settings.'));
        // Android doesn't let apps flip these themselves — be honest about the one tap.
        return Outcome(t('$label ki setting khol di — ${on ? 'on' : 'off'} karne ke liye bas ek tap kijiye.',
            'Android doesn\'t let apps switch $label themselves — I\'ve opened it, one tap turns it ${on ? 'on' : 'off'}.'));

      case 'navigate':
        final place = a['place'] as String;
        if (!await phone.navigate(place)) return Outcome(t('Maps nahi khul paaya.', 'I couldn\'t open Maps.'), status: TurnStatus.failed);
        final where = switch (place) { 'Home' => t('Ghar', 'home'), 'Work' => t('Office', 'work'), _ => _title(place) };
        return Outcome(t(g('$where ka rasta khol raha hoon.', '$where ka rasta khol rahi hoon.'), 'Getting directions to $where.'));

      case 'timer':
        final secs = a['seconds'] as int;
        await phone.setTimer(secs, 'AERIS');
        return Outcome(t('${speakDuration(secs)} ka timer shuru.', 'Timer set for ${speakDuration(secs, hinglish: false)}.'));

      case 'torch':
        final on = a['on'] as bool;
        final ok = await phone.torch(on);
        if (!ok) return Outcome(t('Torch nahi chal paayi.', 'I couldn\'t control the torch.'), status: TurnStatus.failed);
        return Outcome(on ? t('Torch on.', 'Torch on.') : t('Torch off.', 'Torch off.'));

      case 'call':
        // Resolved by prepare() (or a "which one?" answer)
        if (a['number'] case final String number) {
          await phone.dial(number);
          final name = '${a['name'] ?? number}';
          if (name == number) return Outcome(t('$number dial kar diya — bas call dabaiye.', 'Dialing $number — tap call to connect.'));
          return Outcome(t('$name ka number dial kar diya.', 'Dialing $name.'), detail: number);
        }
        final to = a['to'] as String;
        if (looksLikeNumber(to)) {
          await phone.dial(to);
          return Outcome(t('$to dial kar diya — bas call dabaiye.', 'Dialing $to — tap call to connect.'));
        }
        final found = await phone.findPeople(to);
        if (found.isEmpty) {
          return Outcome(t('Contacts mein "$to" nahi mila.', 'I couldn\'t find "$to" in your contacts.'), status: TurnStatus.failed);
        }
        await phone.dial(found.first.number);
        return Outcome(t('${found.first.name} ka number dial kar diya.', 'Dialing ${found.first.name}.'),
            detail: found.first.number);

      case 'message':
        final number = a['number'] as String;
        final body = a['body'] as String;
        if (a['app'] == 'whatsapp') {
          await phone.whatsapp(number, body);
        } else {
          await phone.sms(number, body);
        }
        return Outcome(t('Message ready hai — bas send dabaiye.', 'Your message is ready — just tap send.'));

      case 'open':
        // Not in the built-in list → look among the apps installed on this phone
        var target = a['target'] as String?;
        var name = _title(a['app'] as String);
        if (target == null) {
          final installed = await phone.findApp(a['app'] as String);
          target = installed?.package;
          if (installed != null) name = installed.label; // its real name, not "Angel 1"
        }
        if (target == null || !await phone.openApp(target)) {
          return Outcome(t(g('$name nahi khol paaya.', '$name nahi khol paayi.'), 'I couldn\'t open $name.'), status: TurnStatus.failed);
        }
        return Outcome(t(g('$name khol raha hoon.', '$name khol rahi hoon.'), 'Opening $name.'));

      case 'search':
        final q = a['q'] as String;
        await phone.openUrl('https://www.google.com/search?q=${Uri.encodeComponent(q)}');
        return Outcome(t(g('Google pe dhoondh raha hoon.', 'Google pe dhoondh rahi hoon.'), 'Searching Google.'), detail: q);

      case 'remember':
        store.addMemory(_cap(a['text'] as String));
        return Outcome(t('Yaad rakh liya.', 'Got it, I\'ll remember that.'));

      case 'recall':
        if (a['text'] == null) {
          return Outcome(t('Ye aapne mujhe abhi tak nahi bataya.', "You haven't told me that yet."));
        }
        return Outcome(t('Aapne bataya tha: ${a['text']}', 'You told me: ${a['text']}'));

      case 'math':
        final v = (a['value'] as num).toDouble();
        return Outcome(fmtNum(v), detail: '${a['expr']} = ${fmtNum(v)}');

      case 'greet':
        return Outcome(_name.isEmpty ? t('Haan, boliye.', 'Hi! What can I do?') : t('Haan $_name, boliye.', 'Hi $_name, what can I do?'));
      case 'thanks':
        return Outcome(t('Koi baat nahi.', 'Anytime.'));
      case 'help':
        return Outcome(t(
            g('Main alarm, reminder, timer, call, WhatsApp, gaane, volume, silent, rasta, apps kholna, torch, battery, time, calculation aur cheezein yaad rakhna kar sakta hoon.',
                'Main alarm, reminder, timer, call, WhatsApp, gaane, volume, silent, rasta, apps kholna, torch, battery, time, calculation aur cheezein yaad rakhna kar sakti hoon.'),
            'I can set alarms, reminders and timers, call, message on WhatsApp, play music, change the volume, silence the phone, give directions, open apps, control the torch, tell the time and battery, do maths, and remember things.'));
      case 'who':
        return Outcome(t(g('Main AERIS hoon, aapka assistant. Isi phone pe chalta hoon.', 'Main AERIS hoon, aapki assistant. Isi phone pe chalti hoon.'),
            'I\'m AERIS, your assistant. I run right here on your phone.'));
      case 'howareyou':
        return Outcome(t('Main badhiya hoon! Aap batao, kya karna hai?', 'All good! What do you need?'));
      case 'end':
        return Outcome(t('Theek hai, bye!', 'Okay, bye!'));
      default:
        return Outcome(t('Ye abhi mujhe nahi aata.', 'I can\'t do that yet.'), status: TurnStatus.unknown);
    }
  }

  /// Resume what was playing; if nothing was, start a music app.
  Future<Outcome> _play(String query, String? app) async {
    if (query.isEmpty && app == null && await phone.media('play')) {
      return Outcome(t('Gaana phir se chalu kar diya.', 'Resuming your music.'));
    }
    if (!await phone.playMusic(query, app: app)) {
      return Outcome(t('Gaane ke liye koi music app nahi mila.', 'I couldn\'t find a music app.'), status: TurnStatus.failed);
    }
    if (query.isEmpty) return Outcome(t(g('Gaana chala raha hoon.', 'Gaana chala rahi hoon.'), 'Playing some music.'));
    return Outcome(t(g('${_title(query)} chala raha hoon.', '${_title(query)} chala rahi hoon.'), 'Playing ${_title(query)}.'));
  }

  static const _settingNames = {
    'wifi': 'Wi-Fi',
    'bluetooth': 'Bluetooth',
    'hotspot': 'Hotspot',
    'airplane_mode': 'Airplane mode',
    'location': 'Location',
    'mobile_data': 'Mobile data',
    'battery_saver': 'Battery saver',
    'auto_rotate': 'Auto-rotate',
    'main': 'Phone',
  };

  static bool _sameDay(DateTime a, DateTime b) => a.year == b.year && a.month == b.month && a.day == b.day;
  String _dayHi(DateTime d) {
    final now = DateTime.now();
    if (_sameDay(d, now)) return 'aaj';
    if (_sameDay(d, now.add(const Duration(days: 1)))) return 'kal';
    return _days[d.weekday - 1];
  }

  String _dayEn(DateTime d) {
    final now = DateTime.now();
    if (_sameDay(d, now)) return 'today';
    if (_sameDay(d, now.add(const Duration(days: 1)))) return 'tomorrow';
    return 'on ${_days[d.weekday - 1]}';
  }

  static String _title(String s) => s.isEmpty ? s : s.split(' ').map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}').join(' ');
  static String _cap(String s) => s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';

  static const _days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  static const _months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
}

/// A short human label for a tool (Log screen).
String toolLabel(String tool) => switch (tool) {
      'time' => 'Time',
      'date' => 'Date',
      'battery' => 'Battery',
      'alarm' => 'Alarm',
      'remind' => 'Reminder',
      'cancel_alarm' => 'Alarm off',
      'cancel_timer' => 'Timer off',
      'next_alarm' => 'Next alarm',
      'ringer' => 'Ringer',
      'volume' => 'Volume',
      'media' || 'play' => 'Music',
      'setting' => 'Settings',
      'navigate' => 'Directions',
      'timer' => 'Timer',
      'torch' => 'Torch',
      'call' => 'Call',
      'message' => 'Message',
      'open' => 'Open app',
      'search' => 'Web search',
      'remember' => 'Remembered',
      'recall' => 'Recalled',
      'math' => 'Maths',
      'protocol' => 'Protocol',
      'greet' || 'thanks' || 'who' || 'howareyou' || 'help' => 'Chat',
      'brain' => 'Brain',
      'end' => 'Ended',
      _ => 'Not understood',
    };
