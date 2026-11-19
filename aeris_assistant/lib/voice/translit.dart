/// Turns what the on-device recognizer writes into what the router reads.
///
/// Whisper writes Hindi in Devanagari ("कल सुबह का अलार्म"), English
/// loanwords too ("बैटरी"). The router speaks Hinglish-in-Latin, so this
/// romanises Devanagari the way people type Hinglish (long vowels collapse,
/// final schwa dropped) and then maps common loanword spellings back to
/// English. Pure, so it's unit tested.
library;

const _vowels = {
  'अ': 'a', 'आ': 'a', 'इ': 'i', 'ई': 'i', 'उ': 'u', 'ऊ': 'u', 'ए': 'e', 'ऐ': 'ai',
  'ओ': 'o', 'औ': 'au', 'ऋ': 'ri', 'ऑ': 'o', 'ऍ': 'e',
};
const _matras = {
  'ा': 'a', 'ि': 'i', 'ी': 'i', 'ु': 'u', 'ू': 'u', 'े': 'e', 'ै': 'ai', 'ो': 'o',
  'ौ': 'au', 'ृ': 'ri', 'ॉ': 'o', 'ॅ': 'e',
};
const _consonants = {
  'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'n', 'च': 'ch', 'छ': 'chh', 'ज': 'j',
  'झ': 'jh', 'ञ': 'n', 'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n', 'त': 't',
  'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n', 'प': 'p', 'फ': 'f', 'ब': 'b', 'भ': 'bh',
  'म': 'm', 'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh', 'ष': 'sh', 'स': 's',
  'ह': 'h', 'क़': 'q', 'ख़': 'kh', 'ग़': 'g', 'ज़': 'z', 'ड़': 'r', 'ढ़': 'rh', 'फ़': 'f',
  'य़': 'y',
};
const _halant = '्';
const _nukta = '़';

bool _isDeva(String ch) {
  final c = ch.codeUnitAt(0);
  return c >= 0x0900 && c <= 0x097F;
}

/// Romanise one Devanagari word.
String _word(String w) {
  final out = StringBuffer();
  final chars = w.split('');
  for (var i = 0; i < chars.length; i++) {
    var ch = chars[i];
    if (i + 1 < chars.length && chars[i + 1] == _nukta) {
      ch = '$ch$_nukta';
      i++;
    }
    final cons = _consonants[ch];
    if (cons != null) {
      out.write(cons);
      final next = i + 1 < chars.length ? chars[i + 1] : null;
      final atEnd = next == null;
      // inherent "a" unless a matra/halant follows, or it's the word end
      if (!atEnd && !_matras.containsKey(next) && next != _halant && next != 'ं' && next != 'ँ') {
        out.write('a');
      } else if (next == 'ं' || next == 'ँ') {
        out.write('a');
      }
      continue;
    }
    if (_matras.containsKey(ch)) {
      out.write(_matras[ch]);
      continue;
    }
    if (_vowels.containsKey(ch)) {
      out.write(_vowels[ch]);
      continue;
    }
    if (ch == 'ं' || ch == 'ँ') {
      out.write('n');
      continue;
    }
    if (ch == 'ः') {
      out.write('h');
      continue;
    }
    if (ch == _halant) continue;
    final c = ch.codeUnitAt(0);
    if (c >= 0x0966 && c <= 0x096F) {
      out.write(c - 0x0966);
      continue;
    }
    if (ch == '।' || ch == '॥') {
      out.write('.');
      continue;
    }
    out.write(ch);
  }
  return out.toString();
}

String romanize(String s) {
  if (!s.split('').any(_isDeva)) return s;
  return s.replaceAllMapped(RegExp(r'[ऀ-ॿ]+'), (m) => _word(m[0]!));
}

/// Loanwords as Devanagari-romanised (or misheard) → the English the router
/// knows. Only whole words.
const _loan = <String, String>{
  'alarm': 'alarm', 'alaram': 'alarm', 'alarma': 'alarm', 'alaarm': 'alarm',
  'taimar': 'timer', 'taimara': 'timer', 'taimer': 'timer',
  'tarch': 'torch', 'torcha': 'torch', 'tórch': 'torch',
  'baitari': 'battery', 'baitri': 'battery', 'baitrii': 'battery', 'baetari': 'battery', 'bettery': 'battery',
  'kol': 'call', 'kal karo': 'call karo',
  'vhatsaip': 'whatsapp', 'vhatsep': 'whatsapp', 'vatsaip': 'whatsapp', 'vatsep': 'whatsapp',
  'votsaip': 'whatsapp', 'whatsaip': 'whatsapp', 'whatsap': 'whatsapp', 'whats app': 'whatsapp',
  'yutyub': 'youtube', 'yutyuba': 'youtube', 'yootyoob': 'youtube', 'you tube': 'youtube',
  'mesej': 'message', 'maisej': 'message', 'mesaj': 'message',
  'opan': 'open', 'opana': 'open',
  'sarch': 'search', 'sarcha': 'search',
  'taim': 'time', 'taima': 'time',
  'det': 'date', 'deta': 'date',
  'parsent': 'percent', 'parsenta': 'percent', 'pratishat': 'percent',
  'minat': 'minute', 'minata': 'minute', 'minut': 'minute',
  'sekand': 'second', 'sekanda': 'second',
  'gud': 'good', 'moning': 'morning', 'morning': 'morning', 'marning': 'morning',
  'phon': 'phone', 'fon': 'phone',
  'bai': 'bye', 'baay': 'bye',
  'aun': 'on', 'aaf': 'off', // not "of" → "off": breaks "20 percent of 500"
};

/// Full cleanup for a recognizer transcript.
String cleanTranscript(String raw) {
  var s = romanize(raw.trim());
  s = s.toLowerCase().replaceAll(RegExp(r'[!?,;"“”]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();
  // strip a trailing full stop Whisper likes to add
  s = s.replaceAll(RegExp(r'\.$'), '');
  final words = s.split(' ');
  for (var i = 0; i < words.length; i++) {
    final w = words[i];
    final two = i + 1 < words.length ? '$w ${words[i + 1]}' : null;
    if (two != null && _loan.containsKey(two)) {
      words[i] = _loan[two]!;
      words[i + 1] = '';
      continue;
    }
    if (_loan.containsKey(w)) {
      words[i] = _loan[w]!;
    } else if (w.length >= 6 && !_keep.contains(w)) {
      // one-letter slips on LONG command words only ("whatsap", "batery"). Short
      // words have real neighbours ("touch" is not "torch") — those go through _context.
      for (final v in _vocab) {
        if ((v.length - w.length).abs() <= 1 && _lev(w, v) == 1) {
          words[i] = v;
          break;
        }
      }
    }
  }
  return _context(words.where((w) => w.isNotEmpty).join(' '));
}

/// Mishearings that only make sense in context (measured on the on-device
/// Hinglish model, tool/eval_transcripts.dart).
String _context(String s) {
  // "tour on karo" / "touch band karo" / "toarch bank karo" → torch
  s = s.replaceAllMapped(
      RegExp(r'\b(tour|touch|tourge|toarch|torche|torque|tourch|tarch|torch)\s+(on|off|band|bandh|bank|jalao|bujhao|chalu)\b'),
      (m) => 'torch ${m[2] == 'bank' || m[2] == 'bandh' ? 'band' : m[2]}');
  // "bus" / "bus bus" said alone → "bas" (end)
  s = s.replaceAll(RegExp(r'^(bus|bass|buss)( (bus|bass|buss))?$'), 'bas');
  // "yahaan rakho ki …" at the start → "yaad rakho ki …"
  s = s.replaceAll(RegExp(r'^(yahaan|yahan|yaha|yad|yaad) (rakho|rakhna|rakh lo)\b'), 'yaad rakho');
  // "bhejon / bhairjo / bhaijo / bhajho" → "bhejo"
  s = s.replaceAll(RegExp(r'\bbh(e|a|ai|ay|ey|air)?j(h)?o(n)?\b'), 'bhejo');
  // "aalaan / alaan / aalam" next to time words → "alarm"
  s = s.replaceAll(RegExp(r'\b(aalaan|alaan|aalam|alaam|aalaam|alam|alaram)\b'), 'alarm');
  return s;
}

/// Command words worth snapping to on a 1-letter slip.
const _vocab = [
  'alarm', 'timer', 'torch', 'battery', 'whatsapp', 'youtube', 'message', 'search', 'minute',
  'minutes', 'percent', 'kholo', 'lagao', 'remember', 'instagram', 'flashlight', 'telegram',
  'spotify', 'settings', 'camera', 'chrome', 'google', 'reminder', 'seconds', 'second',
];

/// Real words near a vocab word that must NOT be snapped.
const _keep = {'timers', 'alarms', 'minutes', 'seconds', 'messages', 'search', 'karo', 'later'};

int _lev(String a, String b) {
  final prev = List<int>.generate(b.length + 1, (i) => i);
  for (var i = 1; i <= a.length; i++) {
    var diag = prev[0];
    prev[0] = i;
    for (var j = 1; j <= b.length; j++) {
      final tmp = prev[j];
      prev[j] = [prev[j] + 1, prev[j - 1] + 1, diag + (a[i - 1] == b[j - 1] ? 0 : 1)].reduce((x, y) => x < y ? x : y);
      diag = tmp;
    }
  }
  return prev[b.length];
}
