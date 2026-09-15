/// Date parsing for the handful of forms people write at an assistant.
///
/// Day-first on ambiguity (`3/4/2026` is 3 April, not 4 March) — the user is
/// Indian and writes dates the way most of the world does. ISO `2026-04-03` is
/// still recognised, because it is unambiguous by construction.
library;

const _months = <String, int>{
  'january': 1, 'jan': 1,
  'february': 2, 'feb': 2,
  'march': 3, 'mar': 3,
  'april': 4, 'apr': 4,
  'may': 5,
  'june': 6, 'jun': 6,
  'july': 7, 'jul': 7,
  'august': 8, 'aug': 8,
  'september': 9, 'sep': 9, 'sept': 9,
  'october': 10, 'oct': 10,
  'november': 11, 'nov': 11,
  'december': 12, 'dec': 12,
};

const monthNames = <String>[
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const dayNames = <String>[
  'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
];

/// Matches any of the supported date forms. Exposed so a skill can find a date
/// inside a longer sentence rather than only parsing a whole string.
final datePattern = RegExp(
  r'(\d{4}-\d{1,2}-\d{1,2}'                                  // 2026-08-15
  r'|\d{1,2}\s*[/-]\s*\d{1,2}(?:\s*[/-]\s*\d{2,4})?'         // 15/8 or 15/8/2026
  r'|\d{1,2}(?:st|nd|rd|th)?\s+[a-z]{3,9}\.?(?:\s+\d{2,4})?' // 15 august 2026
  r'|[a-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{2,4})?' // august 15 2026
  r'|today|tomorrow|yesterday|aaj|kal)',
);

/// Parses [src] into a date, or null when it is not one.
///
/// [now] supplies "today" and the implied year, so callers stay testable.
DateTime? parseDate(String src, {required DateTime now}) {
  final s = src.trim().toLowerCase().replaceAll(RegExp(r'[,.]$'), '');
  if (s.isEmpty) return null;

  final today = DateTime(now.year, now.month, now.day);
  switch (s) {
    case 'today':
    case 'aaj':
      return today;
    case 'tomorrow':
      return today.add(const Duration(days: 1));
    case 'yesterday':
      return today.subtract(const Duration(days: 1));
    case 'kal':
      // Hinglish "kal" is both yesterday and tomorrow. Forward is the more
      // common intent when someone is asking an assistant to plan.
      return today.add(const Duration(days: 1));
  }

  // ISO: 2026-08-15
  final iso = RegExp(r'^(\d{4})-(\d{1,2})-(\d{1,2})$').firstMatch(s);
  if (iso != null) {
    return _build(
      int.parse(iso.group(1)!),
      int.parse(iso.group(2)!),
      int.parse(iso.group(3)!),
    );
  }

  // Numeric, day first: 15/8/2026, 15-8-26, 15/8
  final numeric =
      RegExp(r'^(\d{1,2})\s*[/-]\s*(\d{1,2})(?:\s*[/-]\s*(\d{2,4}))?$')
          .firstMatch(s);
  if (numeric != null) {
    final day = int.parse(numeric.group(1)!);
    final month = int.parse(numeric.group(2)!);
    final year = _year(numeric.group(3), now);
    return _build(year, month, day);
  }

  // 15 august 2026 / 15th aug
  final dayFirst =
      RegExp(r'^(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?(?:\s+(\d{2,4}))?$')
          .firstMatch(s);
  if (dayFirst != null) {
    final month = _months[dayFirst.group(2)!];
    if (month == null) return null;
    return _build(
      _year(dayFirst.group(3), now),
      month,
      int.parse(dayFirst.group(1)!),
    );
  }

  // august 15 2026 / aug 15th
  final monthFirst =
      RegExp(r'^([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{2,4}))?$')
          .firstMatch(s);
  if (monthFirst != null) {
    final month = _months[monthFirst.group(1)!];
    if (month == null) return null;
    return _build(
      _year(monthFirst.group(3), now),
      month,
      int.parse(monthFirst.group(2)!),
    );
  }

  return null;
}

int _year(String? raw, DateTime now) {
  if (raw == null) return now.year;
  final v = int.parse(raw);
  if (raw.length <= 2) {
    // Two digits: 98 -> 1998, 26 -> 2026. The pivot sits far enough forward
    // that birth years keep working.
    return v > 50 ? 1900 + v : 2000 + v;
  }
  return v;
}

/// Rejects impossible dates instead of letting DateTime roll them over —
/// `31 february` would otherwise silently become 3 March.
DateTime? _build(int year, int month, int day) {
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  final d = DateTime(year, month, day);
  if (d.year != year || d.month != month || d.day != day) return null;
  return d;
}

String formatDate(DateTime d) => '${d.day} ${monthNames[d.month - 1]} ${d.year}';

String formatDay(DateTime d) => dayNames[d.weekday - 1];

/// Whole days between two dates, ignoring any time component so daylight-saving
/// transitions cannot turn 30 days into 29.97 and round wrong.
int daysBetween(DateTime a, DateTime b) {
  final from = DateTime(a.year, a.month, a.day);
  final to = DateTime(b.year, b.month, b.day);
  return to.difference(from).inDays;
}
