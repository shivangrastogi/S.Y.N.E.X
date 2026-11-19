import 'package:android_intent_plus/android_intent.dart';
import 'package:android_intent_plus/flag.dart';
import 'package:battery_plus/battery_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_contacts/flutter_contacts.dart' as fc;
import 'package:torch_light/torch_light.dart';
import 'package:url_launcher/url_launcher.dart';

import '../voice/translit.dart';
import 'parse.dart' show normalize;

/// A contact match.
class Person {
  const Person(this.name, this.number);
  final String name;
  final String number;
}

/// Everything AERIS can do to the phone. The executor only talks to this,
/// so tests swap in a fake.
abstract class Phone {
  Future<void> setAlarm(int hour, int minute, String label);
  Future<void> setTimer(int seconds, String label);
  Future<void> dial(String number);
  Future<void> whatsapp(String number, String text);
  Future<void> sms(String number, String text);
  Future<void> openUrl(String url);
  Future<bool> openApp(String target);
  Future<bool> torch(bool on);
  Future<({int level, bool charging})?> battery();
  Future<List<Person>> findPeople(String query);

  // ── alarms & timers the Clock app owns ──
  /// Asks the Clock app to remove the alarm at [hour]:[minute]. False = it can't.
  Future<bool> dismissAlarm(int hour, int minute);
  Future<void> showAlarms();
  Future<void> showTimers();

  /// When the next alarm (any app's) will ring, or null if none is set.
  Future<DateTime?> nextAlarm();

  // ── sound ──
  /// 'silent' | 'vibrate' | 'normal'. False = Android needs Do Not Disturb access first.
  Future<bool> setRinger(String mode);
  Future<void> openDndAccess();

  /// 'up' | 'down' | 'mute' | 'unmute' | 'max' | 'set' (with [level] 0..100).
  /// Returns the media volume afterwards in percent, or null on failure.
  Future<int?> volume(String action, {int? level});

  /// 'play' | 'pause' | 'toggle' | 'next' | 'previous'. For play: true when
  /// something is actually playing afterwards.
  Future<bool> media(String action);

  /// Plays [query] (empty = anything) in a music app. False = no app could.
  Future<bool> playMusic(String query, {String? app});

  // ── settings, maps, apps ──
  /// Opens the quick panel / settings page for [which] (wifi, bluetooth, …).
  Future<bool> openSetting(String which);
  Future<bool> navigate(String place);

  /// The installed app whose name best matches [name].
  Future<InstalledApp?> findApp(String name);
}

class AndroidPhone implements Phone {
  final _battery = Battery();
  List<fc.Contact>? _contacts;
  DateTime _contactsAt = DateTime(2000);

  @override
  Future<void> setAlarm(int hour, int minute, String label) => AndroidIntent(
        action: 'android.intent.action.SET_ALARM',
        arguments: <String, dynamic>{
          'android.intent.extra.alarm.HOUR': hour,
          'android.intent.extra.alarm.MINUTES': minute,
          'android.intent.extra.alarm.MESSAGE': label,
          'android.intent.extra.alarm.SKIP_UI': true,
        },
        flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
      ).launch();

  @override
  Future<void> setTimer(int seconds, String label) => AndroidIntent(
        action: 'android.intent.action.SET_TIMER',
        arguments: <String, dynamic>{
          'android.intent.extra.alarm.LENGTH': seconds,
          'android.intent.extra.alarm.MESSAGE': label,
          'android.intent.extra.alarm.SKIP_UI': true,
        },
        flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
      ).launch();

  /// Opens the dialer with the number filled in — the user presses call.
  @override
  Future<void> dial(String number) =>
      AndroidIntent(action: 'android.intent.action.DIAL', data: 'tel:$number').launch();

  @override
  Future<void> whatsapp(String number, String text) => launchUrl(
        Uri.parse('https://wa.me/${waNumber(number)}?text=${Uri.encodeComponent(text)}'),
        mode: LaunchMode.externalApplication,
      );

  @override
  Future<void> sms(String number, String text) =>
      launchUrl(Uri.parse('sms:$number?body=${Uri.encodeComponent(text)}'));

  @override
  Future<void> openUrl(String url) => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

  @override
  Future<bool> openApp(String target) async {
    try {
      if (target.startsWith('action:')) {
        await AndroidIntent(action: target.substring(7), flags: [Flag.FLAG_ACTIVITY_NEW_TASK]).launch();
      } else {
        await AndroidIntent(
          action: 'android.intent.action.MAIN',
          category: 'android.intent.category.LAUNCHER',
          package: target,
          flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
        ).launch();
      }
      return true;
    } catch (e) {
      debugPrint('openApp($target) failed: $e');
      return false;
    }
  }

  @override
  Future<bool> torch(bool on) async {
    try {
      if (!await TorchLight.isTorchAvailable()) return false;
      on ? await TorchLight.enableTorch() : await TorchLight.disableTorch();
      return true;
    } catch (e) {
      debugPrint('torch failed: $e');
      return false;
    }
  }

  @override
  Future<({int level, bool charging})?> battery() async {
    try {
      final level = await _battery.batteryLevel;
      final st = await _battery.batteryState;
      return (level: level, charging: st == BatteryState.charging || st == BatteryState.full);
    } catch (e) {
      debugPrint('battery failed: $e');
      return null;
    }
  }

  @override
  Future<List<Person>> findPeople(String query) async {
    if (!await fc.FlutterContacts.requestPermission(readonly: true)) return const [];
    if (_contacts == null || DateTime.now().difference(_contactsAt).inMinutes >= 5) {
      _contacts = await fc.FlutterContacts.getContacts(withProperties: true);
      _contactsAt = DateTime.now();
    }
    final people = [
      for (final contact in _contacts!)
        if (contact.phones.isNotEmpty) Person(contact.displayName, _bestNumber(contact.phones)),
    ];
    return rankPeople(people, query);
  }

  /// The mobile number if there is one (the first saved may be a landline).
  static String _bestNumber(List<fc.Phone> phones) => phones
      .firstWhere((p) => p.label == fc.PhoneLabel.mobile || p.isPrimary, orElse: () => phones.first)
      .number;

  // ── Clock app ──
  @override
  Future<bool> dismissAlarm(int hour, int minute) async {
    try {
      await AndroidIntent(
        action: 'android.intent.action.DISMISS_ALARM',
        arguments: <String, dynamic>{
          'android.intent.extra.alarm.SEARCH_MODE': 'android.time',
          'android.intent.extra.alarm.HOUR': hour,
          'android.intent.extra.alarm.MINUTES': minute,
        },
        flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
      ).launch();
      return true;
    } catch (e) {
      debugPrint('dismissAlarm failed: $e');
      return false;
    }
  }

  @override
  Future<void> showAlarms() =>
      AndroidIntent(action: 'android.intent.action.SHOW_ALARMS', flags: [Flag.FLAG_ACTIVITY_NEW_TASK]).launch();

  @override
  Future<void> showTimers() =>
      AndroidIntent(action: 'android.intent.action.SHOW_TIMERS', flags: [Flag.FLAG_ACTIVITY_NEW_TASK]).launch();

  // ── native side: android/.../DeviceBridge.kt ──
  static const _device = MethodChannel('aeris/device');

  @override
  Future<DateTime?> nextAlarm() async {
    final ms = await _device.invokeMethod<int>('nextAlarm');
    return ms == null ? null : DateTime.fromMillisecondsSinceEpoch(ms);
  }

  @override
  Future<bool> setRinger(String mode) async => await _device.invokeMethod<bool>('ringer', {'mode': mode}) ?? false;

  @override
  Future<void> openDndAccess() => _device.invokeMethod<void>('openDndAccess');

  @override
  Future<int?> volume(String action, {int? level}) =>
      _device.invokeMethod<int>('volume', {'action': action, 'level': ?level});

  @override
  Future<bool> media(String action) async => await _device.invokeMethod<bool>('media', {'action': action}) ?? false;

  @override
  Future<bool> playMusic(String query, {String? app}) async {
    if (app == 'youtube') {
      await openUrl('https://www.youtube.com/results?search_query=${Uri.encodeComponent(query)}');
      return true;
    }
    final package = switch (app) {
      'spotify' => 'com.spotify.music',
      'youtube_music' => 'com.google.android.apps.youtube.music',
      _ => null,
    };
    try {
      // Android's standard "play this" request — Spotify, YouTube Music and
      // most players start playing straight away.
      await AndroidIntent(
        action: 'android.media.action.MEDIA_PLAY_FROM_SEARCH',
        package: package,
        arguments: <String, dynamic>{'query': query, 'android.intent.extra.focus': 'vnd.android.cursor.item/*'},
        flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
      ).launch();
      return true;
    } catch (e) {
      debugPrint('playMusic failed: $e');
      if (query.isEmpty) return false;
      await openUrl('https://www.youtube.com/results?search_query=${Uri.encodeComponent(query)}');
      return true;
    }
  }

  @override
  Future<bool> openSetting(String which) async {
    // Panels (Android 10+) flip the switch in one tap without leaving AERIS.
    final actions = switch (which) {
      'wifi' => ['android.settings.panel.action.WIFI', 'android.settings.WIFI_SETTINGS'],
      'mobile_data' => ['android.settings.panel.action.INTERNET_CONNECTIVITY', 'android.settings.DATA_ROAMING_SETTINGS'],
      'bluetooth' => ['android.settings.BLUETOOTH_SETTINGS'],
      'airplane_mode' => ['android.settings.AIRPLANE_MODE_SETTINGS'],
      'location' => ['android.settings.LOCATION_SOURCE_SETTINGS'],
      'hotspot' => ['android.settings.WIRELESS_SETTINGS'],
      'battery_saver' => ['android.settings.BATTERY_SAVER_SETTINGS'],
      'display' || 'auto_rotate' => ['android.settings.DISPLAY_SETTINGS'],
      'sound' => ['android.settings.SOUND_SETTINGS'],
      'battery' => ['android.intent.action.POWER_USAGE_SUMMARY'],
      'apps' => ['android.settings.APPLICATION_SETTINGS'],
      'storage' => ['android.settings.INTERNAL_STORAGE_SETTINGS'],
      'notifications' => ['android.settings.ALL_APPS_NOTIFICATION_SETTINGS', 'android.settings.SETTINGS'],
      'security' => ['android.settings.SECURITY_SETTINGS'],
      'accessibility' => ['android.settings.ACCESSIBILITY_SETTINGS'],
      'language' => ['android.settings.LOCALE_SETTINGS'],
      'date_time' => ['android.settings.DATE_SETTINGS'],
      'about' => ['android.settings.DEVICE_INFO_SETTINGS'],
      _ => ['android.settings.SETTINGS'],
    };
    for (final action in actions) {
      try {
        await AndroidIntent(action: action, flags: [Flag.FLAG_ACTIVITY_NEW_TASK]).launch();
        return true;
      } catch (e) {
        debugPrint('openSetting($action) failed: $e');
      }
    }
    return false;
  }

  @override
  Future<bool> navigate(String place) async {
    try {
      await AndroidIntent(
        action: 'android.intent.action.VIEW',
        data: 'google.navigation:q=${Uri.encodeComponent(place)}',
        package: 'com.google.android.apps.maps',
        flags: [Flag.FLAG_ACTIVITY_NEW_TASK],
      ).launch();
      return true;
    } catch (e) {
      debugPrint('navigate (Maps app) failed: $e');
      return launchUrl(
        Uri.parse('https://www.google.com/maps/dir/?api=1&destination=${Uri.encodeComponent(place)}'),
        mode: LaunchMode.externalApplication,
      );
    }
  }

  List<InstalledApp>? _apps;

  @override
  Future<InstalledApp?> findApp(String name) async {
    try {
      _apps ??= [
        for (final app in await _device.invokeListMethod<Map>('apps') ?? const <Map>[])
          (label: '${app['label']}', package: '${app['package']}'),
      ];
      return bestAppMatch(_apps!, name);
    } catch (e) {
      debugPrint('findApp failed: $e');
      return null;
    }
  }
}

typedef InstalledApp = ({String label, String package});

/// The installed app whose label best matches what was said. Pure (tested).
/// Labels go through the router's [normalize] too, so "Angel One" matches
/// the "angel 1" the router hands over.
InstalledApp? bestAppMatch(List<InstalledApp> apps, String said) {
  String n(String s) => normalize(romanize(s)).replaceAll(RegExp(r'[^a-z0-9]'), '');
  final q = n(said);
  if (q.length < 2) return null;
  InstalledApp? best;
  var bestScore = 0;
  for (final app in apps) {
    final label = n(app.label);
    if (label.isEmpty) continue;
    final score = label == q
        ? 3
        : (label.startsWith(q) || (label.length >= 4 && q.startsWith(label)))
            ? 2
            : (q.length >= 4 && label.contains(q))
                ? 1
                : 0;
    if (score > bestScore) {
      bestScore = score;
      best = app;
    }
  }
  return best;
}

/// Family words people say ↔ how contacts are saved. "mummy ko call karo"
/// finds a contact saved as "Maa"; never "mama" (an uncle in Hindi).
const _relations = [
  {'mummy', 'mumma', 'mom', 'mommy', 'mother', 'maa', 'ma', 'mammi', 'ammi', 'mumy', 'mamma'},
  {'papa', 'pappa', 'dad', 'daddy', 'father', 'pitaji', 'pita', 'abbu', 'dady'},
  {'bhai', 'bhaiya', 'bhaiyya', 'brother', 'bro'},
  {'didi', 'di', 'sister', 'behen', 'sis'},
  {'wife', 'biwi', 'patni'},
  {'husband', 'pati'},
];

String _plainName(String s) => romanize(s)
    .toLowerCase()
    .replaceAll(RegExp(r'[^a-z0-9 ]'), '')
    .replaceAll(RegExp(r'\s+'), ' ')
    .trim()
    .replaceAll(RegExp(r'\s+(ji|sir|madam|mam)$'), '');

/// One person's match strength for [query]: 4 exact, 3 first name or a
/// family word, 2 prefix, 1 contained, 0 none.
int personScore(String name, String query) {
  final q = _plainName(query).replaceAll(RegExp(r'\s+(bhai|bhaiya|didi)$'), '');
  final full = _plainName(name);
  if (q.isEmpty || full.isEmpty) return 0;
  final first = full.split(' ').first;
  if (full == q) return 4;
  if (first == q) return 3;
  for (final family in _relations) {
    if (family.contains(q) && (family.contains(full) || family.contains(first))) return 3;
  }
  if (full.startsWith(q)) return 2;
  if (full.contains(q)) return 1;
  return 0;
}

/// Best matches first. Pure, so it's tested without contacts permission.
/// Contacts saved in Hindi script ("पापा") match too.
List<Person> rankPeople(List<Person> people, String query) {
  final scored = <(Person, int)>[
    for (final p in people)
      if (personScore(p.name, query) case final score when score > 0) (p, score),
  ];
  scored.sort((a, b) => b.$2.compareTo(a.$2));
  return [for (final s in scored) s.$1];
}

/// Everyone who matches [query] equally well at the top. More than one
/// means AERIS must ask "which one?" instead of guessing. The same number
/// saved twice counts once.
List<Person> topMatches(List<Person> people, String query) {
  final ranked = rankPeople(people, query);
  if (ranked.isEmpty) return const [];
  final best = personScore(ranked.first.name, query);
  final seen = <String>{};
  return [
    for (final p in ranked)
      if (personScore(p.name, query) == best && seen.add(p.number.replaceAll(RegExp(r'\D'), ''))) p,
  ];
}

/// Which of [options] the user meant: "pehla", "second", "Sharma wale".
/// Null when the answer doesn't single one out.
Person? pickPerson(String said, List<Person> options) {
  final s = romanize(said).toLowerCase().replaceAll(RegExp(r'[^a-z0-9 ]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();
  const ordinals = [
    ['pehla', 'pehle', 'pahla', 'pahle', 'first', 'ek', '1', 'one'],
    ['doosra', 'dusra', 'doosre', 'dusre', 'second', 'do', '2', 'two'],
    ['teesra', 'tisra', 'teesre', 'third', 'teen', '3', 'three'],
  ];
  final words = s.split(' ').toSet();
  for (var i = 0; i < ordinals.length && i < options.length; i++) {
    if (ordinals[i].any(words.contains)) return options[i];
  }
  const filler = {'wala', 'wale', 'wali', 'vala', 'vale', 'waala', 'waale', 'ko', 'ji', 'call', 'karo', 'bhejo', 'number', 'haan', 'vo', 'wo', 'woh'};
  // a word that names exactly one option ("sharma", "office")
  final named = <Person>{};
  for (final w in words) {
    if (w.length < 2 || filler.contains(w)) continue;
    final matching = [for (final o in options) if (personScore(o.name, w) > 0) o];
    if (matching.length == 1) named.add(matching.single);
  }
  return named.length == 1 ? named.single : null;
}

/// "+91 98765 43210" / "098765 43210" / "9876543210" → "919876543210".
String waNumber(String raw) {
  var d = raw.replaceAll(RegExp(r'\D'), '');
  if (d.length == 11 && d.startsWith('0')) d = d.substring(1);
  if (d.length == 10) d = '91$d';
  return d;
}

bool looksLikeNumber(String s) => s.replaceAll(RegExp(r'[\s\-+()]'), '').length >= 7 &&
    RegExp(r'^[\d\s\-+()]+$').hasMatch(s);
