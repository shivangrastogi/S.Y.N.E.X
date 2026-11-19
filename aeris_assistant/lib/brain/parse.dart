/// Pure parsing helpers (no Flutter, no plugins) — fully unit tested.
library;

final _numWords = <String, int>{
  // English
  'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
  'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'fifteen': 15,
  'twenty': 20, 'thirty': 30, 'forty': 40, 'forty five': 45, 'sixty': 60,
  // Hindi (romanised, as Google en-IN tends to write them)
  'ek': 1, 'do': 2, 'teen': 3, 'char': 4, 'chaar': 4, 'paanch': 5, 'panch': 5,
  'chhe': 6, 'chhah': 6, 'cheh': 6, 'saat': 7, 'aath': 8, 'nau': 9, 'das': 10,
  'gyarah': 11, 'barah': 12, 'baarah': 12, 'pandrah': 15, 'bees': 20, 'tees': 30,
  'chalis': 40, 'pachas': 50, 'pachaas': 50,
};

/// Lower-case, strip punctuation (keep ':' '.' '%' between/after digits),
/// collapse spaces, and turn number words into digits.
String normalize(String input) {
  var s = input.toLowerCase().trim();
  s = s.replaceAll(RegExp(r'[“”"‘’`]'), ' ').replaceAll("'", '');
  s = s.replaceAll(RegExp(r'[!?,;]+'), ' ');
  // a full stop that isn't between digits is punctuation
  s = s.replaceAll(RegExp(r'(?<!\d)\.|\.(?!\d)'), ' ');
  s = s.replaceAll(RegExp(r'\s+'), ' ').trim();
  // "forty five" before "forty"
  final keys = _numWords.keys.toList()..sort((a, b) => b.length - a.length);
  for (final w in keys) {
    // "do" is also the verb in "laga do" / "kar do" — only map it when a unit follows.
    if (w == 'do') {
      s = s.replaceAllMapped(
          RegExp(r'\bdo (minute|minutes|min|mins|ghante|ghanta|second|seconds|baje|hours?)\b'),
          (m) => '2 ${m[1]}');
      continue;
    }
    s = s.replaceAll(RegExp('\\b${RegExp.escape(w)}\\b'), '${_numWords[w]}');
  }
  return s;
}

bool hasAny(String s, List<String> words) =>
    words.any((w) => RegExp('(^|\\s)${RegExp.escape(w)}(\\s|\$)').hasMatch(s));

/// A clock time with an optional "tomorrow" hint.
class Clock {
  const Clock(this.hour, this.minute);
  final int hour; // 0..23
  final int minute;

  String get hhmm => '${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')}';

  String get spoken {
    final h12 = hour % 12 == 0 ? 12 : hour % 12;
    final ampm = hour < 12 ? 'a.m.' : 'p.m.'; // written style Shivang asked for
    return '$h12:${minute.toString().padLeft(2, '0')} $ampm';
  }

  @override
  bool operator ==(Object other) => other is Clock && other.hour == hour && other.minute == minute;
  @override
  int get hashCode => Object.hash(hour, minute);
  @override
  String toString() => hhmm;
}

/// Parse a time out of Hinglish/English speech. [now] decides AM/PM when the
/// sentence doesn't say (next occurrence wins).
Clock? parseClock(String s, DateTime now) {
  int? h;
  var m = 0;

  RegExpMatch? x;
  if ((x = RegExp(r'\b(\d{1,2})[:.](\d{2})\b').firstMatch(s)) != null) {
    h = int.parse(x![1]!);
    m = int.parse(x[2]!);
  } else if ((x = RegExp(r'\b(saade|sade|saadhe)\s+(\d{1,2})\b').firstMatch(s)) != null) {
    h = int.parse(x![2]!);
    m = 30;
  } else if ((x = RegExp(r'\b(sava|sawa|sawaa)\s+(\d{1,2})\b').firstMatch(s)) != null) {
    h = int.parse(x![2]!);
    m = 15;
  } else if ((x = RegExp(r'\b(paune|pone)\s+(\d{1,2})\b').firstMatch(s)) != null) {
    h = int.parse(x![2]!) - 1;
    m = 45;
    if (h == 0) h = 12;
  } else if (RegExp(r'\bdedh\b').hasMatch(s)) {
    h = 1;
    m = 30;
  } else if (RegExp(r'\b(dhai|dhaai)\b').hasMatch(s)) {
    h = 2;
    m = 30;
  } else if ((x = RegExp(r'\b(\d{1,2})\s?(am|pm|a m|p m)\b').firstMatch(s)) != null) {
    h = int.parse(x![1]!);
  } else if ((x = RegExp(r'\b(\d{1,2})\s+(\d{2})\b').firstMatch(s)) != null &&
      !RegExp(r'\b\d{1,2}\s+\d{2}\s*(minute|min|second|sec|ghant|hour)').hasMatch(s)) {
    h = int.parse(x![1]!);
    m = int.parse(x[2]!);
  } else if ((x = RegExp(r'\b(\d{1,2})\s*(baje|bje|o ?clock|bajkar)\b').firstMatch(s)) != null) {
    h = int.parse(x![1]!);
  } else if ((x = RegExp(r'\b(at|for|pe|par)\s+(\d{1,2})\b(?!\s*(?:minutes?|mins?|minat|seconds?|secs?|ghant\w*|hours?|hrs?|%|percent))')
          .firstMatch(s)) !=
      null) {
    // "for 5 minutes" is a length, not 5 o'clock (review, 2026-11-17)
    h = int.parse(x![2]!);
  } else if ((x = RegExp(r'\b(\d{1,2})\s+(ka|ke|ki)\s+(alarm)\b').firstMatch(s)) != null) {
    h = int.parse(x![1]!);
  }
  if (h == null || h > 23 || m > 59) return null;

  final am = hasAny(s, ['am', 'a m', 'subah', 'savere', 'sawere', 'morning', 'saverey']);
  final pm = hasAny(s, ['pm', 'p m', 'shaam', 'sham', 'evening', 'dopahar', 'dopehar', 'afternoon', 'tonight']);
  final night = hasAny(s, ['raat', 'night']);
  final tomorrow = hasAny(s, ['kal', 'tomorrow']);

  if (h > 12) return Clock(h, m);
  if (am) return Clock(h == 12 ? 0 : h, m);
  if (pm) return Clock(h == 12 ? 12 : h + 12, m);
  if (night) return Clock(h >= 1 && h <= 4 ? h : (h == 12 ? 0 : h + 12), m);
  if (tomorrow) {
    // "kal 6 baje" — mornings are by far the common case for alarms.
    if (h >= 4 && h <= 11) return Clock(h, m);
    if (h == 12) return Clock(12, m);
    return Clock(h + 12, m);
  }
  // next occurrence of h:m (AM or PM)
  final cands = [Clock(h == 12 ? 0 : h, m), Clock(h == 12 ? 12 : h + 12, m)];
  int minutesUntil(Clock c) {
    final d = (c.hour * 60 + c.minute) - (now.hour * 60 + now.minute);
    return d <= 0 ? d + 1440 : d;
  }

  cands.sort((a, b) => minutesUntil(a).compareTo(minutesUntil(b)));
  return cands.first;
}

/// Total seconds in "5 minute", "1 ghanta 20 min", "aadha ghanta", "90 sec".
int? parseDuration(String s) {
  var total = 0.0;
  var found = false;
  if (RegExp(r'\b(aadha|adha|half an?)\s+(ghanta|ghante|hour)\b').hasMatch(s)) {
    total += 1800;
    found = true;
  }
  if (RegExp(r'\bdedh\s+(ghanta|ghante|hours?)\b').hasMatch(s)) {
    total += 5400; // 1½ — "dedh ghante ka timer" (golden list, 2026-11-17)
    found = true;
  }
  if (RegExp(r'\b(dhai|dhaai)\s+(ghanta|ghante|hours?)\b').hasMatch(s)) {
    total += 9000; // 2½
    found = true;
  }
  final re = RegExp(
      r'(\d+(?:\.\d+)?)\s*(hours?|hrs?|ghante|ghanta|ghanton|h\b|minutes?|mins?|minat|m\b|seconds?|secs?|sec|s\b)');
  for (final x in re.allMatches(s)) {
    final v = double.parse(x[1]!);
    final u = x[2]!;
    final mult = u.startsWith('h') || u.startsWith('g')
        ? 3600
        : u.startsWith('s')
            ? 1
            : 60;
    total += v * mult;
    found = true;
  }
  return found && total > 0 ? total.round() : null;
}

String speakDuration(int seconds, {bool hinglish = true}) {
  final h = seconds ~/ 3600, m = (seconds % 3600) ~/ 60, s = seconds % 60;
  final parts = <String>[];
  if (h > 0) parts.add(hinglish ? '$h ghante' : '$h hour${h == 1 ? '' : 's'}');
  if (m > 0) parts.add(hinglish ? '$m minute' : '$m minute${m == 1 ? '' : 's'}');
  if (s > 0) parts.add(hinglish ? '$s second' : '$s second${s == 1 ? '' : 's'}');
  return parts.join(' ');
}

/// "12 into 8", "15 plus 7", "20 percent of 500", "500 ka 20 percent".
({String expr, double value})? parseMath(String s) {
  const n = r'(-?\d+(?:\.\d+)?)';
  RegExpMatch? x;
  if ((x = RegExp('$n\\s*(%|percent|pratishat) (of|ka|ki|ke) $n').firstMatch(s)) != null) {
    final a = double.parse(x![1]!), b = double.parse(x[4]!);
    return (expr: '${_fmt(a)}% of ${_fmt(b)}', value: a * b / 100);
  }
  if ((x = RegExp('$n (ka|ki|ke) $n\\s*(%|percent|pratishat)').firstMatch(s)) != null) {
    final b = double.parse(x![1]!), a = double.parse(x[3]!);
    return (expr: '${_fmt(a)}% of ${_fmt(b)}', value: a * b / 100);
  }
  final ops = <String, String>{
    r'\+|plus|jod|aur jodo': '+',
    r'-|minus|ghata|less': '−',
    r'x|×|\*|into|times|multiplied by|guna|multiply': '×',
    r'/|÷|divided by|divide by|bata|by': '÷',
  };
  for (final e in ops.entries) {
    x = RegExp('$n\\s*(?:${e.key})\\s*$n').firstMatch(s);
    if (x == null) continue;
    final a = double.parse(x[1]!), b = double.parse(x[2]!);
    final v = switch (e.value) {
      '+' => a + b,
      '−' => a - b,
      '×' => a * b,
      _ => b == 0 ? double.nan : a / b,
    };
    return (expr: '${_fmt(a)} ${e.value} ${_fmt(b)}', value: v);
  }
  return null;
}

String _fmt(double v) => fmtNum(v);

String fmtNum(double v) {
  if (v.isNaN || v.isInfinite) return '—';
  if (v == v.roundToDouble()) return v.toInt().toString();
  return v.toStringAsFixed(v.abs() < 10 ? 3 : 2).replaceFirst(RegExp(r'0+$'), '').replaceFirst(RegExp(r'\.$'), '');
}

/// Words that carry no meaning for memory recall.
const _stop = {
  'meri', 'mera', 'mere', 'my', 'the', 'a', 'an', 'is', 'was', 'hai', 'tha', 'thi', 'ki', 'ka', 'ke',
  'ko', 'kahan', 'kaha', 'where', 'kya', 'what', 'did', 'i', 'me', 'mujhe', 'maine', 'batao', 'bata',
  'yaad', 'remember', 'tell', 'about', 'in', 'mein', 'se', 'kab', 'when', 'pe', 'par', 'to', 'do',
  'karo', 'aur', 'and', 'tum', 'you', 'aapko', 'tumhe', 'hain', 'hoon', 'ho', 'are', 'it', 'that',
};

Set<String> keywords(String s) => normalize(s)
    .split(' ')
    .map((w) => w.replaceAll(RegExp(r'[^a-z0-9]'), ''))
    .where((w) => w.length > 1 && !_stop.contains(w))
    .toSet();
