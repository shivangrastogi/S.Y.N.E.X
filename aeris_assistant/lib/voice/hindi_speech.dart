/// Roman Hinglish (what AERIS shows) → Devanagari (what the Hindi voice reads).
///
/// The JARVIS voice (Supertonic 3, male voice 9) speaks Hinglish naturally only
/// from Devanagari — that's how the sample Shivang picked was made. The screen
/// keeps the Roman text; only the spoken copy is converted. Pure + unit tested.
library;

const _ones = [
  'शून्य', 'एक', 'दो', 'तीन', 'चार', 'पाँच', 'छह', 'सात', 'आठ', 'नौ', 'दस', 'ग्यारह', 'बारह', 'तेरह',
  'चौदह', 'पंद्रह', 'सोलह', 'सत्रह', 'अठारह', 'उन्नीस', 'बीस', 'इक्कीस', 'बाईस', 'तेईस', 'चौबीस',
  'पच्चीस', 'छब्बीस', 'सत्ताईस', 'अट्ठाईस', 'उनतीस', 'तीस', 'इकतीस', 'बत्तीस', 'तैंतीस', 'चौंतीस',
  'पैंतीस', 'छत्तीस', 'सैंतीस', 'अड़तीस', 'उनतालीस', 'चालीस', 'इकतालीस', 'बयालीस', 'तैंतालीस',
  'चवालीस', 'पैंतालीस', 'छियालीस', 'सैंतालीस', 'अड़तालीस', 'उनचास', 'पचास', 'इक्यावन', 'बावन',
  'तिरेपन', 'चौवन', 'पचपन', 'छप्पन', 'सत्तावन', 'अट्ठावन', 'उनसठ', 'साठ', 'इकसठ', 'बासठ', 'तिरेसठ',
  'चौंसठ', 'पैंसठ', 'छियासठ', 'सड़सठ', 'अड़सठ', 'उनहत्तर', 'सत्तर', 'इकहत्तर', 'बहत्तर', 'तिहत्तर',
  'चौहत्तर', 'पचहत्तर', 'छिहत्तर', 'सतहत्तर', 'अठहत्तर', 'उनासी', 'अस्सी', 'इक्यासी', 'बयासी',
  'तिरासी', 'चौरासी', 'पचासी', 'छियासी', 'सत्तासी', 'अट्ठासी', 'नवासी', 'नब्बे', 'इक्यानवे', 'बानवे',
  'तिरानवे', 'चौरानवे', 'पचानवे', 'छियानवे', 'सत्तानवे', 'अट्ठानवे', 'निन्यानवे',
];

/// Whole number → Hindi words (up to crores; longer = digit by digit).
String hindiNumber(int n) {
  if (n < 0) return 'माइनस ${hindiNumber(-n)}';
  if (n < 100) return _ones[n];
  String part(int value, int unit, String name) {
    final head = value ~/ unit, rest = value % unit;
    return rest == 0 ? '${hindiNumber(head)} $name' : '${hindiNumber(head)} $name ${hindiNumber(rest)}';
  }

  if (n < 1000) return part(n, 100, 'सौ');
  if (n < 100000) return part(n, 1000, 'हज़ार');
  if (n < 10000000) return part(n, 100000, 'लाख');
  if (n < 1000000000) return part(n, 10000000, 'करोड़');
  return n.toString().split('').map((d) => _ones[int.parse(d)]).join(' ');
}

String _num(String s) {
  if (s.contains('.')) {
    final p = s.split('.');
    final frac = p[1].split('').map((d) => _ones[int.parse(d)]).join(' ');
    return '${hindiNumber(int.parse(p[0]))} दशमलव $frac';
  }
  // phone-number-like → digit by digit
  if (s.length >= 6) return s.split('').map((d) => _ones[int.parse(d)]).join(' ');
  return hindiNumber(int.parse(s));
}

/// "6:30 a.m." → "सुबह साढ़े छह बजे", "9:04 p.m." → "रात नौ बजकर चार मिनट".
String hindiTime(int h24, int m, {bool withPart = true}) {
  final part = h24 < 4
      ? 'रात'
      : h24 < 12
          ? 'सुबह'
          : h24 < 16
              ? 'दोपहर'
              : h24 < 20
                  ? 'शाम'
                  : 'रात';
  int h12(int h) => h % 12 == 0 ? 12 : h % 12;
  final h = h12(h24);
  final String body;
  if (m == 0) {
    body = '${hindiNumber(h)} बजे';
  } else if (m == 30) {
    body = h == 1 ? 'डेढ़ बजे' : h == 2 ? 'ढाई बजे' : 'साढ़े ${hindiNumber(h)} बजे';
  } else if (m == 15) {
    body = 'सवा ${hindiNumber(h)} बजे';
  } else if (m == 45) {
    final next = h12(h24 + 1);
    body = next == 2 ? 'पौने दो बजे' : 'पौने ${hindiNumber(next)} बजे';
  } else {
    body = '${hindiNumber(h)} बजकर ${hindiNumber(m)} मिनट';
  }
  return withPart ? '$part $body' : body;
}

/// Every word AERIS says, plus common app/day/month names.
const _dict = <String, String>{
  // grammar & common Hinglish
  'abhi': 'अभी', 'ho': 'हो', 'rahe': 'रहे', 'hain': 'हैं', 'hai': 'है', 'aaj': 'आज', 'rahi': 'रही',
  'raha': 'रहा', 'nahi': 'नहीं', 'nahin': 'नहीं', 'ka': 'का', 'ki': 'की', 'ke': 'के', 'ko': 'को',
  'laga': 'लगा', 'diya': 'दिया', 'diye': 'दिए', 'kar': 'कर', 'bas': 'बस', 'mein': 'में', 'mila': 'मिला',
  'khol': 'खोल', 'hoon': 'हूँ', 'pe': 'पे', 'par': 'पर', 'dhoondh': 'ढूँढ', 'yaad': 'याद', 'rakh': 'रख',
  'liya': 'लिया', 'aapne': 'आपने', 'bataya': 'बताया', 'tha': 'था', 'thi': 'थी', 'haan': 'हाँ',
  'boliye': 'बोलिए', 'koi': 'कोई', 'baat': 'बात', 'main': 'मैं', 'aapka': 'आपका', 'aapki': 'आपकी',
  'isi': 'इसी', 'chalta': 'चलता', 'chalti': 'चलती', 'badhiya': 'बढ़िया', 'aap': 'आप', 'batao': 'बताओ',
  'kya': 'क्या', 'karna': 'करना', 'theek': 'ठीक', 'kis': 'किस', 'lagaun': 'लगाऊँ', 'kitne': 'कितने',
  'kisko': 'किसको', 'karun': 'करूँ', 'bhejun': 'भेजूँ', 'ye': 'ये', 'mujhe': 'मुझे', 'aata': 'आता',
  'sakta': 'सकता', 'sakti': 'सकती', 'kholna': 'खोलना', 'aur': 'और', 'cheezein': 'चीज़ें', 'rakhna': 'रखना',
  'ghante': 'घंटे', 'ghanta': 'घंटा', 'bheja': 'भेजा', 'bhej': 'भेज', 'thoda': 'थोड़ा', 'kal': 'कल',
  'subah': 'सुबह', 'shaam': 'शाम', 'raat': 'रात', 'ji': 'जी', 'namaste': 'नमस्ते', 'tayyar': 'तैयार',
  'kaan': 'कान', 'phir': 'फिर', 'se': 'से', 'sunai': 'सुनाई', 'dijiye': 'दीजिए', 'kuch': 'कुछ',
  'chahiye': 'चाहिए', 'paaya': 'पाया', 'paayi': 'पाई', 'padh': 'पढ़', 'dabaiye': 'दबाइए', 'shuru': 'शुरू',
  'gaya': 'गया', 'gayi': 'गई', 'aapke': 'आपके', 'liye': 'लिए', 'karo': 'करो', 'ek': 'एक', 'do': 'दो',
  'bajkar': 'बजकर', 'baje': 'बजे', 'tak': 'तक', 'ab': 'अब', 'yeh': 'यह', 'wo': 'वो', 'jo': 'जो',
  'lagaya': 'लगाया', 'samajh': 'समझ', 'nahin.': 'नहीं', 'chal': 'चल',
  // English words used in Hinglish replies
  'battery': 'बैटरी', 'charging': 'चार्जिंग', 'alarm': 'अलार्म', 'timer': 'टाइमर', 'torch': 'टॉर्च',
  'on': 'ऑन', 'off': 'ऑफ', 'dial': 'डायल', 'call': 'कॉल', 'contacts': 'कॉन्टैक्ट्स', 'number': 'नंबर',
  'message': 'मैसेज', 'ready': 'रेडी', 'send': 'सेंड', 'google': 'गूगल', 'aeris': 'एरिस',
  'assistant': 'असिस्टेंट', 'phone': 'फ़ोन', 'time': 'टाइम', 'search': 'सर्च', 'apps': 'ऐप्स',
  'app': 'ऐप', 'calculation': 'कैलकुलेशन', 'minute': 'मिनट', 'minutes': 'मिनट', 'second': 'सेकंड',
  'seconds': 'सेकंड', 'bye': 'बाय', 'okay': 'ओके', 'ok': 'ओके', 'sorry': 'सॉरी', 'mode': 'मोड',
  'focus': 'फ़ोकस', 'good': 'गुड', 'morning': 'मॉर्निंग', 'night': 'नाइट', 'evening': 'ईवनिंग',
  'percent': 'परसेंट', 'type': 'टाइप', 'mic': 'माइक', 'settings': 'सेटिंग्स', 'permission': 'परमिशन',
  'speech': 'स्पीच', 'recognition': 'रिकग्निशन', 'available': 'अवेलेबल', 'check': 'चेक', 'karein': 'करें',
  'done': 'डन', 'protocol': 'प्रोटोकॉल', 'work': 'वर्क', 'sir': 'सर',
  // apps
  'whatsapp': 'व्हाट्सऐप', 'sms': 'एसएमएस', 'youtube': 'यूट्यूब', 'instagram': 'इंस्टाग्राम',
  'chrome': 'क्रोम', 'maps': 'मैप्स', 'gmail': 'जीमेल', 'spotify': 'स्पॉटिफ़ाई', 'camera': 'कैमरा',
  'telegram': 'टेलीग्राम', 'gemini': 'जेमिनी', 'chatgpt': 'चैटजीपीटी', 'netflix': 'नेटफ़्लिक्स',
  'amazon': 'ऐमेज़ॉन', 'flipkart': 'फ़्लिपकार्ट', 'paytm': 'पेटीएम', 'phonepe': 'फ़ोनपे', 'swiggy': 'स्विगी',
  'zomato': 'ज़ोमैटो', 'uber': 'उबर', 'ola': 'ओला', 'linkedin': 'लिंक्डइन', 'facebook': 'फ़ेसबुक',
  // days & months
  'monday': 'सोमवार', 'tuesday': 'मंगलवार', 'wednesday': 'बुधवार', 'thursday': 'गुरुवार',
  'friday': 'शुक्रवार', 'saturday': 'शनिवार', 'sunday': 'रविवार', 'january': 'जनवरी',
  'february': 'फ़रवरी', 'march': 'मार्च', 'april': 'अप्रैल', 'may': 'मई', 'june': 'जून', 'july': 'जुलाई',
  'august': 'अगस्त', 'september': 'सितंबर', 'october': 'अक्टूबर', 'november': 'नवंबर',
  'december': 'दिसंबर',
};

// ── phonetic fallback for words not in the dictionary (mostly names) ──
const _cons = <String, String>{
  'chh': 'छ', 'kh': 'ख', 'gh': 'घ', 'ch': 'च', 'jh': 'झ', 'th': 'थ', 'dh': 'ध', 'ph': 'फ', 'bh': 'भ',
  'sh': 'श', 'k': 'क', 'g': 'ग', 'c': 'क', 'j': 'ज', 't': 'त', 'd': 'द', 'n': 'न', 'p': 'प', 'f': 'फ़',
  'b': 'ब', 'm': 'म', 'y': 'य', 'r': 'र', 'l': 'ल', 'v': 'व', 'w': 'व', 's': 'स', 'h': 'ह', 'z': 'ज़',
  'q': 'क़', 'x': 'क्स',
};
const _vow = <String, (String, String)>{
  // independent, matra
  'aa': ('आ', 'ा'), 'ai': ('ऐ', 'ै'), 'au': ('औ', 'ौ'), 'ee': ('ई', 'ी'), 'oo': ('ऊ', 'ू'),
  'a': ('अ', ''), 'i': ('इ', 'ि'), 'u': ('उ', 'ु'), 'e': ('ए', 'े'), 'o': ('ओ', 'ो'),
};

String phonetic(String word) {
  final w = word.toLowerCase();
  // names ending "-ang" carry a long vowel: Shivang → शिवांग, Sarang → सारंग-like
  if (w.length > 4 && w.endsWith('ang')) return '${phonetic(w.substring(0, w.length - 3))}ांग';
  final out = StringBuffer();
  var prevCons = false;
  var i = 0;
  String? match(Map<String, Object> m) {
    for (final len in [3, 2, 1]) {
      if (i + len <= w.length && m.containsKey(w.substring(i, i + len))) return w.substring(i, i + len);
    }
    return null;
  }

  while (i < w.length) {
    final v = match(_vow);
    if (v != null) {
      final (ind, matra) = _vow[v]!;
      final atEnd = i + v.length == w.length;
      if (prevCons) {
        // Hinglish spells a final long "aa" as "a" (Sharma, Priya)
        out.write(v == 'a' && atEnd ? 'ा' : matra);
      } else {
        out.write(ind);
      }
      prevCons = false;
      i += v.length;
      continue;
    }
    final c = match(_cons);
    if (c != null) {
      final next = i + c.length < w.length ? w[i + c.length] : '';
      // "n" before another consonant → anusvara (Shivang → शिवंग)
      if (c == 'n' && next.isNotEmpty && !_vow.containsKey(next) && next != 'n' && i > 0) {
        out.write('ं');
        prevCons = false;
      } else {
        if (prevCons) out.write('्');
        out.write(_cons[c]);
        prevCons = true;
      }
      i += c.length;
      continue;
    }
    out.write(w[i]); // digits/punctuation/anything else
    prevCons = false;
    i++;
  }
  return out.toString();
}

/// Full conversion for one reply.
String toSpokenDevanagari(String text) {
  var s = text.replaceAll('—', ',').replaceAll('–', ',');
  // times first ("6:30 AM", "18:45")
  s = s.replaceAllMapped(RegExp(r'\b(\d{1,2}):(\d{2})(?:\s*([ap])\.?\s?m\b\.?)?', caseSensitive: false), (m) {
    var h = int.parse(m[1]!);
    final min = int.parse(m[2]!);
    final ap = m[3] == null ? null : '${m[3]!.toUpperCase()}M';
    if (ap == 'PM' && h < 12) h += 12;
    if (ap == 'AM' && h == 12) h = 0;
    // don't repeat a time-of-day word the sentence already has ("kal subah 6:30 a.m.")
    final before = s.substring(0, m.start).toLowerCase();
    final saysPart = RegExp(r'(subah|savere|sawere|dopahar|shaam|sham|raat|morning|evening|night)\s*$').hasMatch(before);
    return hindiTime(h, min, withPart: !saysPart);
  });
  s = s.replaceAllMapped(RegExp(r'(\d+(?:\.\d+)?)\s*%'), (m) => '${_num(m[1]!)} परसेंट');
  s = s.replaceAllMapped(RegExp(r'\d+(?:\.\d+)?'), (m) => _num(m[0]!));
  // words (keep punctuation as-is; "." → "।" reads as a Hindi sentence end)
  s = s.replaceAllMapped(RegExp(r"[A-Za-z][A-Za-z']*"), (m) {
    final w = m[0]!.replaceAll("'", '');
    return _dict[w.toLowerCase()] ?? phonetic(w);
  });
  return s.replaceAll('.', '।').replaceAll(RegExp(r'\s+'), ' ').trim();
}
