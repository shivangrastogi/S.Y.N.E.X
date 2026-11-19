// Runs the brain's tool calls on the phone. The model proposes, this code
// verifies (contact exists, time parses, app opens) and acts; a failed check
// becomes a spoken explanation, never a wrong action. Every device effect
// goes through [BrainActions] so the mapping is unit-tested with a fake
// (test/brain_executor_test.dart).
import 'package:android_intent_plus/android_intent.dart';
import 'package:android_intent_plus/flag.dart';
import 'package:torch_light/torch_light.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:volume_controller/volume_controller.dart';

import '../assistant/accessibility_bridge.dart';
import '../assistant/app_launcher.dart';
import '../assistant/cloud_brain.dart';
import '../core/lang.dart';
import '../assistant/phone_skills.dart';
import 'calc.dart';
import 'memory_store.dart';

/// What the chat screen does after a call ran.
enum BrainOutcome { done, failed, laptop, endBye, endSleep, cancel }

class BrainResult {
  final String spoken;
  final BrainOutcome outcome;
  final String? payload; // laptop command
  const BrainResult(this.spoken, [this.outcome = BrainOutcome.done, this.payload]);
  bool get ok => outcome != BrainOutcome.failed;
}

/// Every side effect the executor may cause.
abstract class BrainActions {
  Future<void> torch(bool on);
  Future<double> getVolume();
  Future<void> setVolume(double v);
  Future<bool> intent(String action,
      {String? data, Map<String, dynamic>? args, String? package, String? category});
  Future<bool> openUrl(String url);
  Future<List<(String, String)>> contacts(String name);
  Future<bool> openApp(String name);
  Future<PhoneSkillResult?> legacy(String phrase);
  Future<bool> a11yEnabled();
  Future<bool> global(String action);
  Future<bool> scroll(bool forward);
  Future<bool> tap(String target);
  Future<void> media(String key);
  Future<String?> cloud(String prompt);
  Future<void> setLanguage(LangMode m);
  MemoryStore get memory;
  DateTime now();
}

class BrainExecutor {
  BrainExecutor([BrainActions? actions]) : a = actions ?? RealBrainActions();
  final BrainActions a;

  static String t(String hi, String en) => Lang.t(hi, en);

  /// Runs every call in order; replies are joined. Stops at the first
  /// call that hands control elsewhere (laptop / end / cancel).
  Future<BrainResult> runAll(List<Map<String, dynamic>> calls) async {
    final said = <String>[];
    var failed = false;
    for (final c in calls) {
      final r = await run(c['name'] as String, (c['args'] as Map?)?.cast<String, dynamic>() ?? {});
      if (r.spoken.isNotEmpty) said.add(r.spoken);
      if (r.outcome == BrainOutcome.failed) failed = true;
      if (r.outcome != BrainOutcome.done && r.outcome != BrainOutcome.failed) {
        return BrainResult(said.join(' '), r.outcome, r.payload);
      }
    }
    return BrainResult(said.join(' '), failed ? BrainOutcome.failed : BrainOutcome.done);
  }

  Future<BrainResult> run(String name, Map<String, dynamic> args) async {
    String s(String k) => (args[k] as String?)?.trim() ?? '';
    try {
      switch (name) {
        case 'flashlight':
          final on = args['state'] == 'on';
          await a.torch(on);
          return BrainResult(on ? t('Torch on kar diya.', 'Flashlight on.') : t('Torch band kar diya.', 'Flashlight off.'));
        case 'volume':
          return _volume(args['action'] as String, args['level'] as int?);
        case 'brightness':
          await a.intent('android.settings.DISPLAY_SETTINGS');
          return BrainResult(t('Brightness ke liye display settings khol di.',
              'Opened display settings for brightness.'));
        case 'toggle_setting':
          return _toggle(args['setting'] as String, args['state'] as String);
        case 'open_settings':
          return _settingsPage(args['page'] as String);
        case 'battery_status':
          return _legacy('battery');
        case 'date_time':
          return _legacy(switch (args['what']) {
            'date' => "what's the date",
            'day' => 'what day is it',
            _ => 'what time',
          });
        case 'calculate':
          final v = calculate(s('expression'));
          if (v == null) {
            return BrainResult(t('Ye calculation samajh nahi aaya.', "I couldn't work that out."), BrainOutcome.failed);
          }
          return BrainResult(t('${s('expression')} = ${prettyNumber(v)}.', 'That\'s ${prettyNumber(v)}.'));
        case 'set_alarm':
          return _alarm(s('time'), label: s('label'), days: s('days'));
        case 'set_timer':
          return _timer(s('duration'), label: s('label'));
        case 'set_reminder':
          return _reminder(s('text'), s('when'));
        case 'create_calendar_event':
          return _calendar(s('title'), s('when'), s('location'));
        case 'call':
          return _call(args);
        case 'send_message':
          return _message(args, withText: true);
        case 'open_chat':
          return _message(args, withText: false);
        case 'send_email':
          return _email(s('to'), s('subject'), s('body'));
        case 'open_app':
          return _openApp(s('app'));
        case 'web_search':
          final q = s('query');
          final yt = args['engine'] == 'youtube';
          await a.openUrl(yt
              ? 'https://www.youtube.com/results?search_query=${Uri.encodeComponent(q)}'
              : 'https://www.google.com/search?q=${Uri.encodeComponent(q)}');
          return BrainResult(t('${yt ? 'YouTube' : 'Google'} pe "$q" dhoond raha hoon.',
              'Searching ${yt ? 'YouTube' : 'Google'} for "$q".'));
        case 'play_music':
          return _music(s('query'), args['app'] as String?);
        case 'media_control':
          final act = args['action'] as String;
          await a.media(switch (act) { 'next' => 'next', 'previous' => 'prev', _ => 'playpause' });
          return BrainResult(switch (act) {
            'next' => t('Agla gaana.', 'Next track.'),
            'previous' => t('Pichla gaana.', 'Previous track.'),
            _ => t('Ho gaya.', 'Done.'),
          });
        case 'take_screenshot':
          return _legacy('screenshot');
        case 'navigate_phone':
          return _a11y(() => a.global(args['action'] as String), switch (args['action']) {
            'back' => t('Wapas.', 'Back.'),
            'home' => 'Home.',
            'recents' => 'Recent apps.',
            'notifications' => t('Notifications khol diye.', 'Opened notifications.'),
            'quick_settings' => 'Quick settings.',
            _ => t('Screen lock kar di.', 'Screen locked.'),
          });
        case 'scroll':
          final up = args['direction'] == 'up';
          return _a11y(() => a.scroll(!up), up ? t('Upar.', 'Scrolled up.') : t('Neeche.', 'Scrolled down.'));
        case 'read_screen':
          return _legacy('read the screen');
        case 'summarize_screen':
          return _legacy('summarize this screen');
        case 'tap_on':
          final target = s('target');
          return _a11y(() => a.tap(target), t('"$target" pe tap kar diya.', 'Tapped "$target".'),
              fail: t('"$target" screen pe nahi mila.', 'I couldn\'t find "$target" on the screen.'));
        case 'camera':
          return _camera(args['mode'] as String?);
        case 'navigate_to':
          return _navigate(s('destination'), args['mode'] as String?);
        case 'remember':
          await a.memory.add(s('fact'));
          return BrainResult(t('Yaad rakh liya.', 'Got it, I\'ll remember that.'));
        case 'recall':
          final hits = await a.memory.search(s('query'));
          if (hits.isEmpty) {
            return BrainResult(t('Iske baare mein mujhe kuch yaad nahi.', 'I don\'t have anything saved about that.'));
          }
          return BrainResult(hits.map((m) => m.text).join('. '));
        case 'forget':
          final gone = await a.memory.forget(s('query'));
          return BrainResult(gone.isEmpty
              ? t('Aisa kuch yaad hi nahi tha.', 'I didn\'t have that saved.')
              : t('Bhool gaya: ${gone.first.text}', 'Forgotten: ${gone.first.text}'));
        case 'create_note':
          await a.memory.add(s('text'), kind: 'note');
          return BrainResult(t('Note bana liya.', 'Noted.'));
        case 'translate':
          return _translate(s('text'), s('target_language'));
        case 'set_language':
          final m = switch (args['mode']) {
            'english_in' => LangMode.englishIn,
            'english_us' => LangMode.englishUs,
            _ => LangMode.hinglish,
          };
          await a.setLanguage(m);
          return BrainResult(m == LangMode.hinglish ? 'Theek hai, ab Hinglish mein baat karenge.' : 'Okay, English from now on.');
        case 'laptop_command':
          return BrainResult('', BrainOutcome.laptop, s('command'));
        case 'end_conversation':
          return BrainResult(t('Theek hai, bye!', 'Okay, bye!'),
              args['mode'] == 'sleep' ? BrainOutcome.endSleep : BrainOutcome.endBye);
        case 'cancel_task':
          return BrainResult(t('Theek hai, cancel.', 'Okay, cancelled.'), BrainOutcome.cancel);
      }
      return BrainResult(t('Ye abhi main nahi kar sakta.', 'I can\'t do that yet.'), BrainOutcome.failed);
    } catch (e) {
      return BrainResult(t('Ye kaam nahi ho paya: $e', 'That didn\'t work: $e'), BrainOutcome.failed);
    }
  }

  // ── helpers ─────────────────────────────────────────────────────────
  Future<BrainResult> _legacy(String phrase) async {
    final r = await a.legacy(phrase);
    if (r == null) return BrainResult(t('Nahi ho paya.', 'That didn\'t work.'), BrainOutcome.failed);
    return BrainResult(r.spoken, r.ok ? BrainOutcome.done : BrainOutcome.failed);
  }

  Future<BrainResult> _a11y(Future<bool> Function() act, String ok, {String? fail}) async {
    if (!await a.a11yEnabled()) {
      return BrainResult(
          t('Screen control off hai. Assistant settings mein "Screen control" on karo.',
              'Screen control is off. Turn it on in Assistant settings.'),
          BrainOutcome.failed);
    }
    return await act()
        ? BrainResult(ok)
        : BrainResult(fail ?? t('Nahi ho paya.', 'That didn\'t work.'), BrainOutcome.failed);
  }

  Future<BrainResult> _volume(String action, int? level) async {
    double target;
    switch (action) {
      case 'mute':
        await a.setVolume(0);
        return BrainResult(t('Volume mute kar diya.', 'Volume muted.'));
      case 'max':
        target = 1.0;
      case 'set':
        target = ((level ?? 50) / 100).clamp(0.0, 1.0);
      case 'unmute':
        final cur = await a.getVolume();
        target = cur > 0.05 ? cur : 0.5;
      default:
        final cur = await a.getVolume();
        target = (cur + (action == 'down' ? -0.2 : 0.2)).clamp(0.0, 1.0);
    }
    await a.setVolume(target);
    final pct = (target * 100).round();
    return BrainResult(t('Volume $pct percent.', 'Volume at $pct percent.'));
  }

  static const _panels = {
    'wifi': ('android.settings.panel.action.WIFI', 'WiFi'),
    'mobile_data': ('android.settings.panel.action.INTERNET_CONNECTIVITY', 'Mobile data'),
    'bluetooth': ('android.settings.BLUETOOTH_SETTINGS', 'Bluetooth'),
    'airplane_mode': ('android.settings.AIRPLANE_MODE_SETTINGS', 'Aeroplane mode'),
    'location': ('android.settings.LOCATION_SOURCE_SETTINGS', 'Location'),
    'hotspot': ('android.settings.TETHER_SETTINGS', 'Hotspot'),
    'dnd': ('android.settings.ZEN_MODE_SETTINGS', 'Do Not Disturb'),
    'auto_rotate': ('android.settings.DISPLAY_SETTINGS', 'Auto rotate'),
    'battery_saver': ('android.settings.BATTERY_SAVER_SETTINGS', 'Battery saver'),
  };

  Future<BrainResult> _toggle(String setting, String state) async {
    final (action, label) = _panels[setting]!;
    if (!await a.intent(action)) await a.intent('android.settings.WIRELESS_SETTINGS');
    // Android 10+ lets no app flip these silently — the panel is one tap.
    return BrainResult(t('$label ka panel khol diya — ek tap mein ${state == 'off' ? 'band' : 'on'} karo.',
        'Opened $label. One tap to turn it ${state == 'off' ? 'off' : 'on'}.'));
  }

  static const _pages = {
    'main': 'android.settings.SETTINGS',
    'wifi': 'android.settings.WIFI_SETTINGS',
    'bluetooth': 'android.settings.BLUETOOTH_SETTINGS',
    'display': 'android.settings.DISPLAY_SETTINGS',
    'sound': 'android.settings.SOUND_SETTINGS',
    'battery': 'android.intent.action.POWER_USAGE_SUMMARY',
    'apps': 'android.settings.MANAGE_APPLICATIONS_SETTINGS',
    'storage': 'android.settings.INTERNAL_STORAGE_SETTINGS',
    'location': 'android.settings.LOCATION_SOURCE_SETTINGS',
    'notifications': 'android.settings.ALL_APPS_NOTIFICATION_SETTINGS',
    'security': 'android.settings.SECURITY_SETTINGS',
    'accessibility': 'android.settings.ACCESSIBILITY_SETTINGS',
    'language': 'android.settings.LOCALE_SETTINGS',
    'date_time': 'android.settings.DATE_SETTINGS',
    'about': 'android.settings.DEVICE_INFO_SETTINGS',
  };

  Future<BrainResult> _settingsPage(String page) async {
    if (!await a.intent(_pages[page]!)) await a.intent('android.settings.SETTINGS');
    return BrainResult(t('Settings khol di.', 'Opened settings.'));
  }

  /// [hour, minute] for a time span; "kal"/"tomorrow" doesn't change it.
  List<int>? _time(String span) => span.isEmpty ? null : PhoneSkills.parseTime(span);

  Future<BrainResult> _alarm(String time, {String label = '', String days = ''}) async {
    final hm = _time(time);
    if (hm == null) {
      await a.intent('android.intent.action.SET_ALARM');
      return BrainResult(t('Alarm app khol diya — time set karo.', 'Opened the alarm app. Set the time there.'));
    }
    await a.intent('android.intent.action.SET_ALARM', args: {
      'android.intent.extra.alarm.HOUR': hm[0],
      'android.intent.extra.alarm.MINUTES': hm[1],
      if (label.isNotEmpty) 'android.intent.extra.alarm.MESSAGE': label,
      // Repeat days need the clock app's own UI; one-off alarms skip it.
      'android.intent.extra.alarm.SKIP_UI': days.isEmpty,
    });
    final hhmm = '${hm[0].toString().padLeft(2, '0')}:${hm[1].toString().padLeft(2, '0')}';
    return BrainResult(days.isEmpty
        ? t('$hhmm ka alarm laga diya.', 'Alarm set for $hhmm.')
        : t('$hhmm ka alarm khul gaya — $days ke liye repeat select karo.',
            'Alarm for $hhmm is open. Pick the repeat days ($days) and save.'));
  }

  Future<BrainResult> _timer(String duration, {String label = ''}) async {
    final secs = duration.isEmpty ? null : PhoneSkills.parseDuration(duration);
    if (secs == null) {
      await a.intent('android.intent.action.SET_TIMER');
      return BrainResult(t('Timer app khol diya.', 'Opened the timer app.'));
    }
    await a.intent('android.intent.action.SET_TIMER', args: {
      'android.intent.extra.alarm.LENGTH': secs,
      if (label.isNotEmpty) 'android.intent.extra.alarm.MESSAGE': label,
      'android.intent.extra.alarm.SKIP_UI': true,
    });
    final m = secs ~/ 60, sec = secs % 60;
    final h = m ~/ 60, mm = m % 60;
    final parts = [if (h > 0) '$h hour', if (mm > 0) '$mm minute', if (sec > 0) '$sec second'];
    return BrainResult(t('${parts.join(' ')} ka timer laga diya.', 'Timer set for ${parts.join(' ')}.'));
  }

  bool _tomorrow(String when) => RegExp(r'\b(kal|tomorrow)\b', caseSensitive: false).hasMatch(when);

  /// Epoch ms for a spoken time today (or tomorrow if said / already past).
  int? _epoch(String when) {
    final hm = _time(when);
    if (hm == null) return null;
    final n = a.now();
    var d = DateTime(n.year, n.month, n.day, hm[0], hm[1]);
    if (_tomorrow(when) || d.isBefore(n)) d = d.add(const Duration(days: 1));
    return d.millisecondsSinceEpoch;
  }

  Future<BrainResult> _reminder(String text, String when) async {
    final hm = _time(when);
    if (hm != null && !_tomorrow(when)) {
      // A labelled alarm rings even offline — the most reliable reminder.
      final r = await _alarm(when, label: text);
      return BrainResult(t('${hm[0]}:${hm[1].toString().padLeft(2, '0')} pe yaad dila dunga: $text.',
          'I\'ll remind you at ${hm[0]}:${hm[1].toString().padLeft(2, '0')}: $text.'), r.outcome);
    }
    return _calendar(text, when, '', reminder: true);
  }

  Future<BrainResult> _calendar(String title, String when, String location, {bool reminder = false}) async {
    final begin = _epoch(when);
    await a.intent('android.intent.action.INSERT', data: 'content://com.android.calendar/events', args: {
      'title': title,
      if (location.isNotEmpty) 'eventLocation': location,
      if (begin != null) 'beginTime': begin,
      if (begin != null) 'endTime': begin + 30 * 60 * 1000,
    });
    final what = reminder ? t('Reminder', 'Reminder') : t('Event', 'Event');
    return BrainResult(t('$what calendar mein ready hai — save dabao.', '$what is ready in your calendar. Tap save.'));
  }

  Future<(String, String)?> _target(Map<String, dynamic> args) async {
    final number = ((args['number'] as String?) ?? '').replaceAll(RegExp(r'[^0-9+]'), '');
    if (number.length >= 7) return (number, number);
    final name = ((args['contact'] as String?) ?? '').trim();
    if (name.isEmpty) return null;
    final hits = await a.contacts(name);
    return hits.isEmpty ? null : hits.first;
  }

  BrainResult _noContact(Map<String, dynamic> args) {
    final name = (args['contact'] ?? args['number'] ?? '').toString();
    return BrainResult(t('"$name" contact list mein nahi mila.', 'I couldn\'t find "$name" in your contacts.'),
        BrainOutcome.failed);
  }

  Future<BrainResult> _call(Map<String, dynamic> args) async {
    final target = await _target(args);
    if (target == null) return _noContact(args);
    final (name, number) = target;
    if (args['app'] == 'whatsapp' || args['video'] == true) {
      // WhatsApp exposes no public call intent — open the chat, one tap away.
      await a.openUrl('https://wa.me/${PhoneSkills.intlNumber(number)}');
      return BrainResult(t('$name ki WhatsApp chat khol di — ${args['video'] == true ? 'video' : 'call'} button dabao.',
          'Opened WhatsApp for $name. Tap the ${args['video'] == true ? 'video' : 'call'} button.'));
    }
    await a.intent('android.intent.action.CALL', data: 'tel:$number');
    return BrainResult(t('$name ko call kar raha hoon.', 'Calling $name.'));
  }

  Future<BrainResult> _message(Map<String, dynamic> args, {required bool withText}) async {
    final target = await _target(args);
    if (target == null) return _noContact(args);
    final (name, number) = target;
    final text = withText ? ((args['message'] as String?) ?? '').trim() : '';
    final app = args['app'] as String? ?? 'whatsapp';
    if (app == 'sms') {
      await a.openUrl('smsto:$number${text.isEmpty ? '' : '?body=${Uri.encodeComponent(text)}'}');
      return BrainResult(t('$name ko SMS ready — send dabao.', 'SMS to $name is ready. Tap send.'));
    }
    if (app == 'telegram') {
      await a.openUrl('tg://resolve?phone=${PhoneSkills.intlNumber(number)}');
      return BrainResult(t('$name ki Telegram chat khol di${text.isEmpty ? '' : ' — message: $text'}.',
          'Opened Telegram for $name${text.isEmpty ? '' : '. Message: $text'}.'));
    }
    // The user taps send themselves — AERIS never sends on its own here.
    await a.openUrl('https://wa.me/${PhoneSkills.intlNumber(number)}'
        '${text.isEmpty ? '' : '?text=${Uri.encodeComponent(text)}'}');
    return BrainResult(text.isEmpty
        ? t('$name ki WhatsApp chat khol di.', 'Opened WhatsApp for $name.')
        : t('$name ko WhatsApp message ready hai — send dabao.', 'Message to $name is ready on WhatsApp. Tap send.'));
  }

  Future<BrainResult> _email(String to, String subject, String body) async {
    final q = [
      if (subject.isNotEmpty) 'subject=${Uri.encodeComponent(subject)}',
      if (body.isNotEmpty) 'body=${Uri.encodeComponent(body)}',
    ].join('&');
    final addr = to.contains('@') ? to.replaceAll(' ', '') : '';
    await a.openUrl('mailto:$addr${q.isEmpty ? '' : '?$q'}');
    return BrainResult(addr.isNotEmpty
        ? t('Email ready hai — send dabao.', 'Your email is ready. Tap send.')
        : t('Email khol diya — $to ka address daalo.', 'Email is open. Add $to\'s address and send.'));
  }

  Future<BrainResult> _openApp(String app) async {
    if (app.isEmpty) return BrainResult(t('Kaunsa app kholun?', 'Which app should I open?'), BrainOutcome.failed);
    // The rule-based skill knows settings/camera/Play Store fallbacks.
    final legacy = await a.legacy('$app kholo');
    if (legacy != null && legacy.ok) return BrainResult(legacy.spoken);
    if (await a.openApp(app)) return BrainResult(t('$app khol diya.', 'Opened $app.'));
    return BrainResult(t('"$app" naam ka app nahi mila.', 'I couldn\'t find an app called "$app".'), BrainOutcome.failed);
  }

  Future<BrainResult> _music(String query, String? app) async {
    final q = Uri.encodeComponent(query);
    switch (app) {
      case 'spotify':
        await a.openUrl(query.isEmpty ? 'spotify:' : 'spotify:search:$q');
      case 'youtube_music':
        await a.openUrl(query.isEmpty ? 'https://music.youtube.com' : 'https://music.youtube.com/search?q=$q');
      default:
        await a.openUrl(query.isEmpty ? 'https://www.youtube.com' : 'https://www.youtube.com/results?search_query=$q');
    }
    return BrainResult(query.isEmpty ? t('Music khol diya.', 'Opening music.') : t('"$query" chala raha hoon.', 'Playing "$query".'));
  }

  Future<BrainResult> _camera(String? mode) async {
    switch (mode) {
      case 'video':
        await a.intent('android.media.action.VIDEO_CAMERA');
      case 'scan':
        if (!await a.openApp('lens')) await a.intent('android.media.action.STILL_IMAGE_CAMERA');
      case 'selfie':
        await a.intent('android.media.action.STILL_IMAGE_CAMERA', args: {
          'android.intent.extras.CAMERA_FACING': 1,
          'android.intent.extras.LENS_FACING_FRONT': 1,
          'android.intent.extra.USE_FRONT_CAMERA': true,
        });
      default:
        await a.intent('android.media.action.STILL_IMAGE_CAMERA');
    }
    return BrainResult(t('Camera khol diya.', 'Opened the camera.'));
  }

  Future<BrainResult> _navigate(String dest, String? mode) async {
    final q = Uri.encodeComponent(dest);
    if (mode == 'transit') {
      await a.openUrl('https://www.google.com/maps/dir/?api=1&destination=$q&travelmode=transit');
    } else {
      final m = switch (mode) { 'walking' => 'w', 'two_wheeler' => 'l', _ => 'd' };
      if (!await a.openUrl('google.navigation:q=$q&mode=$m')) {
        await a.openUrl('https://www.google.com/maps/dir/?api=1&destination=$q');
      }
    }
    return BrainResult(t('$dest ka raasta khol diya.', 'Starting directions to $dest.'));
  }

  Future<BrainResult> _translate(String text, String lang) async {
    final ans = await a.cloud('Translate into $lang. Reply with only the translation:\n$text');
    if (ans != null && ans.trim().isNotEmpty) return BrainResult(ans.trim());
    await a.openUrl('https://translate.google.com/?sl=auto&tl=${Uri.encodeComponent(lang)}'
        '&text=${Uri.encodeComponent(text)}&op=translate');
    return BrainResult(t('Google Translate khol diya.', 'Opened Google Translate.'));
  }
}

/// The real device.
class RealBrainActions implements BrainActions {
  @override
  Future<void> torch(bool on) => on ? TorchLight.enableTorch() : TorchLight.disableTorch();
  @override
  Future<double> getVolume() => VolumeController.instance.getVolume();
  @override
  Future<void> setVolume(double v) async => VolumeController.instance.setVolume(v);

  @override
  Future<bool> intent(String action,
      {String? data, Map<String, dynamic>? args, String? package, String? category}) async {
    try {
      await AndroidIntent(
        action: action,
        data: data,
        arguments: args,
        package: package,
        category: category,
        flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
      ).launch();
      return true;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<bool> openUrl(String url) async {
    try {
      return await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    } catch (_) {
      return false;
    }
  }

  @override
  Future<List<(String, String)>> contacts(String name) => PhoneSkills.findContacts(name);
  @override
  Future<bool> openApp(String name) => AppLauncher.launch(name);
  @override
  Future<PhoneSkillResult?> legacy(String phrase) => PhoneSkills.handle(phrase);
  @override
  Future<bool> a11yEnabled() => AccessibilityBridge.isEnabled();
  @override
  Future<bool> global(String action) => AccessibilityBridge.global(action);
  @override
  Future<bool> scroll(bool forward) => AccessibilityBridge.scroll(forward: forward);
  @override
  Future<bool> tap(String target) => AccessibilityBridge.tap(target);
  @override
  Future<void> media(String key) => AccessibilityBridge.media(key);

  @override
  Future<String?> cloud(String prompt) async =>
      await CloudBrain.isConfigured ? await CloudBrain.ask(prompt) : null;

  @override
  Future<void> setLanguage(LangMode m) => Lang.set(m);
  @override
  MemoryStore get memory => MemoryStore.instance;
  @override
  DateTime now() => DateTime.now();
}
