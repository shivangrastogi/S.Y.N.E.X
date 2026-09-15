// Phase A2 — Tier-1 on-device skills. These run entirely on the phone with
// NO laptop and NO internet: torch, volume, open app, call, WhatsApp, SMS,
// alarm, timer, web search, settings panels.
//
// Design mirrors the laptop's pattern-unification rule: ONE owner per phrase.
// Each skill exposes a pure `matches(lower)` predicate so a unit test can
// prove no utterance is claimed by two skills (see test/phone_skills_test).
// `handle()` tries skills in priority order and returns:
//   - null            → not a phone skill; caller falls through to the laptop
//                        (Tier 2) or the cloud brain (Tier 3)
//   - PhoneSkillResult → handled on-device; `spoken` is AERIS's reply
import 'dart:async';
import 'package:android_intent_plus/android_intent.dart';
import 'package:android_intent_plus/flag.dart';
import 'package:flutter_contacts/flutter_contacts.dart';
import 'package:torch_light/torch_light.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:volume_controller/volume_controller.dart';
import 'accessibility_bridge.dart';
import 'aeris_log.dart';
import 'app_launcher.dart';
import 'cloud_brain.dart';
import 'package:battery_plus/battery_plus.dart';

class PhoneSkillResult {
  final String spoken;
  final bool ok;
  const PhoneSkillResult(this.spoken, {this.ok = true});
}

typedef PhoneSkillRun = Future<PhoneSkillResult> Function(
    String raw, String lower);

class PhoneSkill {
  final String name;
  final bool Function(String lower) matches;
  final PhoneSkillRun run;
  const PhoneSkill(this.name, this.matches, this.run);
}

class PhoneSkills {
  /// Priority order — first match wins. `openApp` is deliberately last
  /// because "kholo/open" is the most generic verb.
  static const List<PhoneSkill> skills = [
    PhoneSkill('torch', _mTorch, _rTorch),
    PhoneSkill('volume', _mVolume, _rVolume),
    // Phase A9 instant offline answers (before alarm/timer so "battery kitni"
    // etc. never fall to a heavier tier).
    PhoneSkill('battery', _mBattery, _rBattery),
    PhoneSkill('datetime', _mDateTime, _rDateTime),
    PhoneSkill('math', _mMath, _rMath),
    PhoneSkill('screenshot', _mShot, _rShot),
    PhoneSkill('alarm', _mAlarm, _rAlarm),
    PhoneSkill('timer', _mTimer, _rTimer),
    PhoneSkill('whatsapp', _mWhatsApp, _rWhatsApp),
    PhoneSkill('sms', _mSms, _rSms),
    PhoneSkill('call', _mCall, _rCall),
    // Phase A5 media + screen control. media before search so "agla gaana"
    // (control) doesn't get caught by search; "gaana chalao" (new song)
    // stays with search because media only matches explicit control verbs.
    PhoneSkill('media', _mMedia, _rMedia),
    PhoneSkill('a11yGlobal', _mGlobal, _rGlobal),
    PhoneSkill('a11yScroll', _mScroll, _rScroll),
    PhoneSkill('a11ySummarise', _mSummarise, _rSummarise),
    PhoneSkill('a11yRead', _mRead, _rRead),
    PhoneSkill('a11yTap', _mTap, _rTap),
    // search before settings: "internet pe search karo" is a search, not a
    // WiFi-panel open. search before openApp: "youtube pe X" searches, while
    // bare "youtube kholo" (no query) falls through to openApp.
    PhoneSkill('search', _mSearch, _rSearch),
    PhoneSkill('settings', _mSettings, _rSettings),
    PhoneSkill('openApp', _mOpenApp, _rOpenApp),
  ];

  /// Name of the skill that would own this command (first match wins), or
  /// null if it falls through to the laptop/cloud. Pure — used by tests.
  static String? firstMatch(String raw) {
    final lower = raw.toLowerCase().trim();
    for (final s in skills) {
      if (s.matches(lower)) return s.name;
    }
    return null;
  }

  /// All skills whose matcher fires (to surface accidental overlaps).
  static List<String> allMatches(String raw) {
    final lower = raw.toLowerCase().trim();
    return [for (final s in skills) if (s.matches(lower)) s.name];
  }

  /// Returns the reply if a phone skill handled the command, else null.
  static Future<PhoneSkillResult?> handle(String raw) async {
    final lower = raw.toLowerCase().trim();
    for (final s in skills) {
      if (s.matches(lower)) {
        try {
          return await s.run(raw, lower);
        } catch (e) {
          AerisLog.add('skill:${s.name}', e);
          return PhoneSkillResult('Ye kaam nahi ho paya: $e', ok: false);
        }
      }
    }
    return null;
  }

  // ── helpers ───────────────────────────────────────────────────────
  static bool _has(String s, List<String> any) => any.any(s.contains);

  static bool _off(String s) =>
      _has(s, ['off', 'band', 'bujha', 'bujhao', 'hata', 'close', 'stop']);

  /// Raw substring (case preserved) after the first of [keys] in [lower].
  static String _after(String raw, String lower, List<String> keys) {
    var best = -1;
    for (final k in keys) {
      final i = lower.indexOf(k);
      if (i >= 0 && (best < 0 || i < best)) best = i + k.length;
    }
    return best < 0 ? '' : raw.substring(best).trim();
  }

  static String _strip(String s, List<String> words) {
    for (final w in words) {
      s = s.replaceAll(RegExp('\\b${RegExp.escape(w)}\\b'), ' ');
    }
    return s.replaceAll(RegExp(r'\s+'), ' ').trim();
  }

  // ── torch ─────────────────────────────────────────────────────────
  static bool _mTorch(String s) =>
      _has(s, ['torch', 'flashlight', 'flash light', 'roshni', 'batti']);
  static Future<PhoneSkillResult> _rTorch(String raw, String lower) async {
    if (_off(lower)) {
      await TorchLight.disableTorch();
      return const PhoneSkillResult('Torch band kar diya.');
    }
    await TorchLight.enableTorch();
    return const PhoneSkillResult('Torch on kar diya.');
  }

  // ── volume ────────────────────────────────────────────────────────
  static bool _mVolume(String s) =>
      _has(s, ['volume', 'awaaz', 'aawaz', 'awaz', 'sound', 'mute',
            'silent karo', 'silent kar']);
  static Future<PhoneSkillResult> _rVolume(String raw, String lower) async {
    final vc = VolumeController.instance;
    if (_has(lower, ['mute', 'silent', 'band', 'chup'])) {
      vc.setVolume(0);
      return const PhoneSkillResult('Volume mute kar diya.');
    }
    final cur = await vc.getVolume();
    if (_has(lower, ['max', 'full', 'poora', 'pura'])) {
      vc.setVolume(1.0);
      return const PhoneSkillResult('Volume full kar diya.');
    }
    final down = _has(lower, ['down', 'kam', 'ghata', 'ghatao', 'neeche']);
    final next = (cur + (down ? -0.2 : 0.2)).clamp(0.0, 1.0);
    vc.setVolume(next);
    return PhoneSkillResult(
        'Volume ${down ? "kam" : "badha"} diya, ${(next * 100).round()} percent.');
  }

  // ── settings panels ───────────────────────────────────────────────
  static bool _mSettings(String s) =>
      _has(s, ['wifi', 'wi-fi', 'bluetooth', 'hotspot', 'mobile data',
            'internet', 'brightness', 'do not disturb', 'dnd',
            'aeroplane', 'airplane', 'flight mode', 'location', 'gps']);
  static Future<PhoneSkillResult> _rSettings(String raw, String lower) async {
    String action;
    String what;
    if (_has(lower, ['bluetooth'])) {
      action = 'android.settings.BLUETOOTH_SETTINGS';
      what = 'Bluetooth';
    } else if (_has(lower, ['brightness'])) {
      action = 'android.settings.DISPLAY_SETTINGS';
      what = 'Brightness';
    } else if (_has(lower, ['do not disturb', 'dnd'])) {
      action = 'android.settings.ZEN_MODE_SETTINGS';
      what = 'Do Not Disturb';
    } else if (_has(lower, ['aeroplane', 'airplane', 'flight'])) {
      action = 'android.settings.AIRPLANE_MODE_SETTINGS';
      what = 'Aeroplane mode';
    } else if (_has(lower, ['location', 'gps'])) {
      action = 'android.settings.LOCATION_SOURCE_SETTINGS';
      what = 'Location';
    } else if (_has(lower, ['hotspot'])) {
      action = 'android.settings.WIRELESS_SETTINGS';
      what = 'Hotspot';
    } else {
      // wifi / internet / mobile data
      action = 'android.settings.WIFI_SETTINGS';
      what = 'WiFi';
    }
    await AndroidIntent(action: action, flags: [Flag.FLAG_ACTIVITY_NEW_TASK])
        .launch();
    // Android 10+ blocks silent toggling, so we open the panel for one tap.
    return PhoneSkillResult('$what settings khol diya — ek tap mein toggle karo.');
  }

  // ── alarm ─────────────────────────────────────────────────────────
  static bool _mAlarm(String s) => s.contains('alarm');
  static Future<PhoneSkillResult> _rAlarm(String raw, String lower) async {
    final t = _parseTime(lower);
    if (t == null) {
      await const AndroidIntent(
              action: 'android.intent.action.SET_ALARM',
              flags: [Flag.FLAG_ACTIVITY_NEW_TASK])
          .launch();
      return const PhoneSkillResult('Alarm app khol diya — time set karo.');
    }
    await AndroidIntent(
      action: 'android.intent.action.SET_ALARM',
      arguments: {
        'android.intent.extra.alarm.HOUR': t[0],
        'android.intent.extra.alarm.MINUTES': t[1],
        'android.intent.extra.alarm.SKIP_UI': true,
      },
      flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
    ).launch();
    final hh = t[0].toString().padLeft(2, '0');
    final mm = t[1].toString().padLeft(2, '0');
    return PhoneSkillResult('$hh:$mm ka alarm laga diya.');
  }

  // ── timer ─────────────────────────────────────────────────────────
  static bool _mTimer(String s) => s.contains('timer');
  static Future<PhoneSkillResult> _rTimer(String raw, String lower) async {
    final secs = _parseDuration(lower);
    if (secs == null) {
      await const AndroidIntent(
              action: 'android.intent.action.SET_TIMER',
              flags: [Flag.FLAG_ACTIVITY_NEW_TASK])
          .launch();
      return const PhoneSkillResult('Timer app khol diya.');
    }
    await AndroidIntent(
      action: 'android.intent.action.SET_TIMER',
      arguments: {
        'android.intent.extra.alarm.LENGTH': secs,
        'android.intent.extra.alarm.SKIP_UI': true,
      },
      flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
    ).launch();
    final m = secs ~/ 60, s = secs % 60;
    final label = m > 0 ? '$m minute${s > 0 ? " $s second" : ""}' : '$s second';
    return PhoneSkillResult('$label ka timer laga diya.');
  }

  // ── whatsapp ──────────────────────────────────────────────────────
  // Requires a target (a contact/message); bare "whatsapp kholo" is left to
  // openApp so the two never collide.
  static bool _mWhatsApp(String s) =>
      _has(s, ['whatsapp', 'whats app', 'wp pe', 'w app']) &&
      _has(s, ['bolo', 'bhejo', 'message', 'msg', 'likho', 'send', 'bol do',
            'keh do', 'text']);
  static Future<PhoneSkillResult> _rWhatsApp(String raw, String lower) async {
    final msg = _after(raw, lower,
        ['bhejo', 'bolo', 'likho', 'send', 'bol do', 'keh do', 'message', 'msg']);
    // Contact = words before "whatsapp", minus filler.
    final before = lower.split(RegExp(r'whats\s*app')).first;
    final name = _strip(before, ['ko', 'ko bolo', 'please', 'aeris', 'par', 'pe', ' pe']);
    final number = await _resolveNumber(name);
    if (number == null) {
      return PhoneSkillResult('"$name" contact list mein nahi mila.', ok: false);
    }
    final uri = Uri.parse(
        'https://wa.me/${_intl(number)}?text=${Uri.encodeComponent(msg)}');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
    return PhoneSkillResult(
        '$name ko WhatsApp khol diya${msg.isEmpty ? "" : ", message ready hai"} — send dabao.');
  }

  // ── sms ───────────────────────────────────────────────────────────
  static bool _mSms(String s) =>
      _has(s, ['sms', 'text message']) ||
      (_has(s, ['message bhejo', 'msg bhejo', 'message karo']) &&
          !_has(s, ['whatsapp', 'whats app']));
  static Future<PhoneSkillResult> _rSms(String raw, String lower) async {
    final msg = _after(raw, lower,
        ['bhejo', 'bolo', 'likho', 'send', 'message', 'msg', 'text']);
    final before = lower.split(RegExp(r'\b(sms|message|msg|text)\b')).first;
    final name = _strip(before, ['ko', 'please', 'aeris', 'send', 'bhejo']);
    final number = await _resolveNumber(name);
    if (number == null) {
      return PhoneSkillResult('"$name" contact nahi mila.', ok: false);
    }
    final uri = Uri.parse('smsto:$number?body=${Uri.encodeComponent(msg)}');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
    return PhoneSkillResult('$name ko SMS ready — send dabao.');
  }

  // ── call ──────────────────────────────────────────────────────────
  static bool _mCall(String s) =>
      _has(s, ['call', 'phone lagao', 'phone karo', 'dial', 'milao',
            'phone kar']) &&
      !_has(s, ['whatsapp', 'whats app', 'video call']);
  static Future<PhoneSkillResult> _rCall(String raw, String lower) async {
    final name = _strip(lower, [
      'please', 'aeris', 'ko', 'call', 'karo', 'kar do', 'kardo', 'phone',
      'lagao', 'laga do', 'dial', 'milao', 'kar', 'de'
    ]);
    final digits = name.replaceAll(RegExp(r'[^0-9+]'), '');
    String? number = digits.length >= 7 ? digits : await _resolveNumber(name);
    if (number == null) {
      return PhoneSkillResult('"$name" contact list mein nahi mila.', ok: false);
    }
    await AndroidIntent(
      action: 'android.intent.action.CALL',
      data: 'tel:$number',
      flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
    ).launch();
    return PhoneSkillResult('$name ko call kar raha hoon.');
  }

  // ── web search ────────────────────────────────────────────────────
  // Explicit search only — "youtube pe X", "google karo X", or a music
  // request. A bare "youtube kholo" (no query verb) is left to openApp, and
  // a plain question ("mausam kaisa hai") falls through to the laptop/cloud.
  static bool _mSearch(String s) =>
      (s.contains('youtube') &&
          _has(s, ['pe', 'par', 'search', 'play', 'chalao', 'bajao',
                'dekho', 'lagao', 'gaana', 'gana', 'song', 'video'])) ||
      _has(s, ['google karo', 'google kar', 'search karo', 'search kar',
            'net pe search', 'internet pe search', 'youtube pe']) ||
      (_has(s, ['gaana', 'gana', 'song', 'music']) &&
          _has(s, ['chalao', 'bajao', 'play', 'lagao', 'sunao', 'suna do']));
  static Future<PhoneSkillResult> _rSearch(String raw, String lower) async {
    final isYt = _has(lower, ['youtube', 'gaana', 'gana', 'song', 'music']);
    final q = _strip(lower, [
      'youtube', 'pe', 'par', 'google', 'karo', 'kar', 'search', 'net',
      'internet', 'dhundo', 'khojo', 'chalao', 'bajao', 'play', 'laga do',
      'lagao', 'sunao', 'suna do', 'please', 'aeris', 'do', 'gaana', 'gana',
      'song', 'music', 'video'
    ]);
    final url = isYt
        ? (q.isEmpty
            ? 'https://www.youtube.com'
            : 'https://www.youtube.com/results?search_query=${Uri.encodeComponent(q)}')
        : 'https://www.google.com/search?q=${Uri.encodeComponent(q)}';
    await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    final where = isYt ? 'YouTube' : 'Google';
    return PhoneSkillResult(
        q.isEmpty ? '$where khol diya.' : '$where pe "$q" khol diya.');
  }

  // ── open app ──────────────────────────────────────────────────────
  static const Map<String, String> _apps = {
    'youtube': 'com.google.android.youtube',
    'whatsapp': 'com.whatsapp',
    'instagram': 'com.instagram.android',
    'insta': 'com.instagram.android',
    'chrome': 'com.android.chrome',
    'gmail': 'com.google.android.gm',
    'maps': 'com.google.android.apps.maps',
    'google maps': 'com.google.android.apps.maps',
    'spotify': 'com.spotify.music',
    'photos': 'com.google.android.apps.photos',
    'gallery': 'com.google.android.apps.photos',
    'play store': 'com.android.vending',
    'playstore': 'com.android.vending',
    'facebook': 'com.facebook.katana',
    'telegram': 'org.telegram.messenger',
    'paytm': 'net.one97.paytm',
    'gpay': 'com.google.android.apps.nbu.paisa.user',
    'google pay': 'com.google.android.apps.nbu.paisa.user',
    'phonepe': 'com.phonepe.app',
    'amazon': 'in.amazon.mShop.android.shopping',
    'flipkart': 'com.flipkart.android',
    'netflix': 'com.netflix.mediaclient',
    'settings': '__settings__',
    'camera': '__camera__',
    'calculator': 'com.google.android.calculator',
    'clock': 'com.google.android.deskclock',
    'calendar': 'com.google.android.calendar',
  };
  static bool _mOpenApp(String s) =>
      _has(s, ['kholo', 'khol do', 'open', 'chalu karo', 'chala do',
            'chalao', 'launch', 'start karo']);
  static Future<PhoneSkillResult> _rOpenApp(String raw, String lower) async {
    // Find which known app name appears.
    String? pkg;
    String? label;
    for (final e in _apps.entries) {
      if (lower.contains(e.key)) {
        pkg = e.value;
        label = e.key;
        break;
      }
    }
    if (pkg == null) {
      final name = _strip(lower,
          ['kholo', 'khol do', 'open', 'chalu karo', 'chala do', 'chalao',
            'launch', 'start karo', 'karo', 'do', 'app', 'please', 'aeris']);
      if (name.isEmpty) {
        return const PhoneSkillResult('Kaunsa app kholun?', ok: false);
      }
      // Not in the fast map → match ANY installed app by its label.
      if (await AppLauncher.launch(name)) {
        return PhoneSkillResult('$name khol diya.');
      }
      return PhoneSkillResult(
          '"$name" naam ka app nahi mila. Naam aur clearly bolo.',
          ok: false);
    }
    if (pkg == '__settings__') {
      await const AndroidIntent(
              action: 'android.settings.SETTINGS',
              flags: [Flag.FLAG_ACTIVITY_NEW_TASK])
          .launch();
      return const PhoneSkillResult('Settings khol diya.');
    }
    if (pkg == '__camera__') {
      await const AndroidIntent(
              action: 'android.media.action.STILL_IMAGE_CAMERA',
              flags: [Flag.FLAG_ACTIVITY_NEW_TASK])
          .launch();
      return const PhoneSkillResult('Camera khol diya.');
    }
    try {
      await AndroidIntent(
        action: 'android.intent.action.MAIN',
        category: 'android.intent.category.LAUNCHER',
        package: pkg,
        flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
      ).launch();
      return PhoneSkillResult('$label khol diya.');
    } catch (_) {
      // Not installed → offer it on the Play Store.
      await launchUrl(Uri.parse('market://details?id=$pkg'),
          mode: LaunchMode.externalApplication);
      return PhoneSkillResult('$label installed nahi hai — Play Store khol diya.');
    }
  }

  // ── Phase A9: battery ─────────────────────────────────────────────
  static bool _mBattery(String s) =>
      _has(s, ['battery', 'charge kitni', 'kitni charge', 'charging']);
  static Future<PhoneSkillResult> _rBattery(String raw, String lower) async {
    final b = Battery();
    final lvl = await b.batteryLevel;
    final st = await b.batteryState;
    final charging =
        st == BatteryState.charging || st == BatteryState.full;
    return PhoneSkillResult(
        'Battery $lvl percent hai${charging ? ", charge ho rahi hai" : ""}.');
  }

  // ── Phase A9: time / date ─────────────────────────────────────────
  static bool _mDateTime(String s) =>
      _has(s, ['time kya', 'kya time', 'kitne baj', 'kitna baja',
            'samay kya', 'what time']) ||
      _has(s, ['aaj kaun', 'aaj ki date', 'aaj konsa', 'aaj kaunsa',
            'kaunsa din', 'konsa din', 'date kya', 'what date', 'day kya']);
  static Future<PhoneSkillResult> _rDateTime(String raw, String lower) async {
    final now = DateTime.now();
    final wantDate = _has(lower, ['date', 'din', 'day', 'aaj', 'tareekh']);
    const days = ['Somwar', 'Mangalwar', 'Budhwar', 'Guruwar', 'Shukrawar',
      'Shaniwar', 'Ravivar'];
    const months = ['January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'];
    if (wantDate) {
      return PhoneSkillResult(
          'Aaj ${days[now.weekday - 1]}, ${now.day} ${months[now.month - 1]} '
          '${now.year} hai.');
    }
    var h = now.hour;
    final ampm = h < 12 ? 'subah' : (h < 17 ? 'dopahar' : (h < 20 ? 'shaam' : 'raat'));
    var h12 = h % 12;
    if (h12 == 0) h12 = 12;
    final mm = now.minute.toString().padLeft(2, '0');
    return PhoneSkillResult('Abhi $ampm $h12 baj ke $mm minute hue hain.');
  }

  // ── Phase A9: quick math ──────────────────────────────────────────
  static bool _mMath(String s) =>
      RegExp(r'\d').hasMatch(s) &&
      _has(s, ['plus', 'jama', 'minus', 'ghata', 'into', 'guna', 'multiply',
            'divide', 'bhaag', 'percent', 'pratishat', '%', 'add karo',
            'jod', 'times']);
  static Future<PhoneSkillResult> _rMath(String raw, String lower) async {
    final nums = RegExp(r'\d+(?:\.\d+)?')
        .allMatches(lower)
        .map((m) => double.parse(m.group(0)!))
        .toList();
    if (nums.length < 2) {
      return const PhoneSkillResult('Do numbers bolo, phir calculate karun.',
          ok: false);
    }
    final a = nums[0], b = nums[1];
    double r;
    String op;
    if (_has(lower, ['percent', 'pratishat', '%'])) {
      r = a / 100 * b;
      op = '$a percent of $b';
    } else if (_has(lower, ['minus', 'ghata'])) {
      r = a - b;
      op = '$a minus $b';
    } else if (_has(lower, ['into', 'guna', 'multiply', 'times'])) {
      r = a * b;
      op = '$a into $b';
    } else if (_has(lower, ['divide', 'bhaag'])) {
      r = b != 0 ? a / b : double.nan;
      op = '$a divide $b';
    } else {
      r = a + b;
      op = '$a plus $b';
    }
    final pretty = r == r.roundToDouble() ? r.toInt().toString()
        : r.toStringAsFixed(2);
    return PhoneSkillResult('$op = $pretty.');
  }

  // ── Phase A9: screenshot (via a11y global action) ─────────────────
  static bool _mShot(String s) =>
      _has(s, ['screenshot', 'screen shot', 'screen capture']);
  static Future<PhoneSkillResult> _rShot(String raw, String lower) async {
    if (!await AccessibilityBridge.isEnabled()) {
      return const PhoneSkillResult(
          'Screenshot ke liye "Screen control" on karo (Assistant settings).',
          ok: false);
    }
    final ok = await AccessibilityBridge.global('screenshot');
    return PhoneSkillResult(ok ? 'Screenshot le liya.' : 'Nahi ho paya.',
        ok: ok);
  }

  // ── Phase A5: media control (via MediaSession keys) ───────────────
  static bool _mMedia(String s) => _has(s, [
        'pause karo', 'pause kar', 'rok do', 'ruk ja', 'gaana rok',
        'gana rok', 'gaana band', 'gana band', 'music band', 'music rok',
        'agla gaana', 'agla gana', 'next song', 'next track', 'next gaana',
        'pichla gaana', 'pichla gana', 'previous song', 'resume karo',
        'music resume', 'play pause', 'gaana chalu rakho'
      ]);
  static Future<PhoneSkillResult> _rMedia(String raw, String lower) async {
    if (_has(lower, ['agla', 'next'])) {
      await AccessibilityBridge.media('next');
      return const PhoneSkillResult('Agla gaana.');
    }
    if (_has(lower, ['pichla', 'previous'])) {
      await AccessibilityBridge.media('prev');
      return const PhoneSkillResult('Pichla gaana.');
    }
    // pause / rok / band / play-pause / resume all toggle play-pause.
    await AccessibilityBridge.media('playpause');
    return const PhoneSkillResult('Ho gaya.');
  }

  // ── Phase A5: global nav (needs the AccessibilityService) ─────────
  static bool _mGlobal(String s) => _has(s, [
        'back jao', 'wapas jao', 'peeche jao', 'go back',
        'home jao', 'home button', 'ghar jao',
        'recent apps', 'recents kholo', 'recent kholo',
        'notification kholo', 'notification dikhao', 'notifications kholo',
        'quick settings'
      ]);
  static Future<PhoneSkillResult> _rGlobal(String raw, String lower) async {
    final guard = await _a11yGuard();
    if (guard != null) return guard;
    String act, say;
    if (_has(lower, ['back', 'wapas', 'peeche'])) {
      act = 'back';
      say = 'Wapas.';
    } else if (_has(lower, ['home', 'ghar'])) {
      act = 'home';
      say = 'Home.';
    } else if (_has(lower, ['recent'])) {
      act = 'recents';
      say = 'Recent apps.';
    } else if (_has(lower, ['quick'])) {
      act = 'quick_settings';
      say = 'Quick settings.';
    } else {
      act = 'notifications';
      say = 'Notifications khol diye.';
    }
    final ok = await AccessibilityBridge.global(act);
    return PhoneSkillResult(ok ? say : 'Nahi ho paya.', ok: ok);
  }

  // ── Phase A5: scroll ──────────────────────────────────────────────
  static bool _mScroll(String s) =>
      s.contains('scroll') ||
      _has(s, ['neeche karo', 'niche karo', 'upar karo', 'thoda neeche',
            'thoda upar']);
  static Future<PhoneSkillResult> _rScroll(String raw, String lower) async {
    final guard = await _a11yGuard();
    if (guard != null) return guard;
    final up = _has(lower, ['upar', 'up', 'peeche', 'back']);
    final ok = await AccessibilityBridge.scroll(forward: !up);
    return PhoneSkillResult(
        ok ? (up ? 'Upar.' : 'Neeche.') : 'Scroll nahi hua.',
        ok: ok);
  }

  // ── Phase A5: summarise the current screen (screen text → Gemini) ─
  static bool _mSummarise(String s) =>
      (_has(s, ['screen', 'page', 'ye', 'is']) &&
          _has(s, ['summarise', 'summarize', 'summary', 'samjhao',
                'samajhao', 'matlab kya'])) ||
      _has(s, ['ye kya likha', 'is page ko summarise', 'screen summarise']);
  static Future<PhoneSkillResult> _rSummarise(String raw, String lower) async {
    final guard = await _a11yGuard();
    if (guard != null) return guard;
    final text = await AccessibilityBridge.readScreen();
    if (text.isEmpty) {
      return const PhoneSkillResult('Screen pe kuch padhne layak nahi mila.',
          ok: false);
    }
    if (!await CloudBrain.isConfigured) {
      // No cloud brain → at least read a short head of the screen.
      final head = text.length > 300 ? text.substring(0, 300) : text;
      return PhoneSkillResult('Screen pe ye likha hai: $head');
    }
    final ans = await CloudBrain.ask(
        'Is screen ke content ko 2 line mein Hinglish mein summarise karo:\n\n$text');
    return PhoneSkillResult(ans);
  }

  // ── Phase A5: read the screen aloud ───────────────────────────────
  static bool _mRead(String s) => _has(s, [
        'screen padho', 'ye padho', 'yeh padho', 'read screen',
        'screen read', 'kya likha hai', 'padh ke sunao'
      ]);
  static Future<PhoneSkillResult> _rRead(String raw, String lower) async {
    final guard = await _a11yGuard();
    if (guard != null) return guard;
    final text = await AccessibilityBridge.readScreen();
    if (text.isEmpty) {
      return const PhoneSkillResult('Screen pe kuch nahi mila.', ok: false);
    }
    final head = text.length > 500 ? '${text.substring(0, 500)}…' : text;
    return PhoneSkillResult(head);
  }

  // ── Phase A5: tap an element by its label ─────────────────────────
  static bool _mTap(String s) =>
      _has(s, ['pe tap', 'pe click', 'pe dabao', 'ko dabao', 'ko tap',
            'button dabao', 'click karo']);
  static Future<PhoneSkillResult> _rTap(String raw, String lower) async {
    final guard = await _a11yGuard();
    if (guard != null) return guard;
    final target = _strip(lower, [
      'pe tap karo', 'pe tap', 'pe click karo', 'pe click', 'pe dabao',
      'ko dabao', 'ko tap karo', 'ko tap', 'button dabao', 'click karo',
      'tap karo', 'dabao', 'button', 'please', 'aeris'
    ]);
    if (target.isEmpty) {
      return const PhoneSkillResult('Kis cheez pe tap karun?', ok: false);
    }
    final ok = await AccessibilityBridge.tap(target);
    return PhoneSkillResult(
        ok ? '"$target" pe tap kar diya.' : '"$target" screen pe nahi mila.',
        ok: ok);
  }

  /// Returns a "please enable" result if the a11y service is off, else null.
  static Future<PhoneSkillResult?> _a11yGuard() async {
    if (await AccessibilityBridge.isEnabled()) return null;
    return const PhoneSkillResult(
        'Screen control off hai. Assistant settings mein "Screen control" '
        'enable karo, phir dubara bolo.',
        ok: false);
  }

  // ── contact resolution (A7: cached, not reloaded every call) ───────
  // The whole address book was being fetched with properties on EVERY
  // call/SMS/WhatsApp — slow and ANR-prone on big lists. Cache it once with a
  // short TTL; refreshed lazily on the next lookup after it expires.
  static List<MapEntry<String, String>>? _contactCache; // (lowerName, number)
  static DateTime _contactCacheAt = DateTime.fromMillisecondsSinceEpoch(0);
  static const _contactTtl = Duration(minutes: 5);

  static Future<void> _ensureContacts() async {
    final fresh = _contactCache != null &&
        DateTime.now().difference(_contactCacheAt) < _contactTtl;
    if (fresh) return;
    if (!await FlutterContacts.requestPermission(readonly: true)) return;
    final contacts = await FlutterContacts.getContacts(withProperties: true);
    final flat = <MapEntry<String, String>>[];
    for (final c in contacts) {
      if (c.phones.isEmpty) continue;
      final num = c.phones.first.number.replaceAll(RegExp(r'\s'), '');
      if (num.isNotEmpty) flat.add(MapEntry(c.displayName.toLowerCase(), num));
    }
    _contactCache = flat;
    _contactCacheAt = DateTime.now();
  }

  static Future<String?> _resolveNumber(String name) async {
    name = name.trim().toLowerCase();
    if (name.isEmpty) return null;
    await _ensureContacts();
    final cache = _contactCache;
    if (cache == null || cache.isEmpty) return null;
    String? partial;
    for (final e in cache) {
      if (e.key == name) return e.value;        // exact wins immediately
      partial ??= e.key.contains(name) ? e.value : null;
    }
    return partial;
  }

  /// wa.me needs a country code + no symbols. Assume +91 for bare 10-digit.
  static String _intl(String number) {
    var d = number.replaceAll(RegExp(r'[^0-9]'), '');
    if (d.length == 10) d = '91$d';
    return d;
  }

  // ── parsers ───────────────────────────────────────────────────────
  /// Returns [hour24, minute] or null.
  static List<int>? _parseTime(String s) {
    final m = RegExp(r'(\d{1,2})(?:[:.](\d{2}))?\s*(baje|bajke|o.?clock|am|pm)?')
        .firstMatch(s);
    if (m == null) return null;
    var h = int.parse(m.group(1)!);
    var min = m.group(2) != null ? int.parse(m.group(2)!) : 0;
    if (s.contains('saade')) min = 30;
    if (s.contains('paune')) {
      h = h == 1 ? 12 : h - 1;
      min = 45;
    }
    if (s.contains('sava')) min = 15;
    final pm = _has(s, ['pm', 'shaam', 'sham', 'raat', 'evening', 'night', 'dopahar']);
    final am = _has(s, ['am', 'subah', 'morning', 'savere']);
    if (pm && h < 12) h += 12;
    if (am && h == 12) h = 0;
    if (h > 23 || min > 59) return null;
    return [h, min];
  }

  static int? _parseDuration(String s) {
    var total = 0;
    final hr = RegExp(r'(\d+)\s*(hour|ghant|ghanta|ghante)').firstMatch(s);
    final mi = RegExp(r'(\d+)\s*(minute|minut|min)').firstMatch(s);
    final se = RegExp(r'(\d+)\s*(second|sec|sekand)').firstMatch(s);
    if (hr != null) total += int.parse(hr.group(1)!) * 3600;
    if (mi != null) total += int.parse(mi.group(1)!) * 60;
    if (se != null) total += int.parse(se.group(1)!);
    return total > 0 ? total : null;
  }
}
