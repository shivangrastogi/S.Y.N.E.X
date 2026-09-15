import '../skill.dart';
import '../utterance.dart';
import 'date_parse.dart';

/// Arithmetic on real dates: gaps, countdowns, ages, and shifting a date.
///
/// Complements [TimeSkill], which answers about *now*. This one only claims an
/// utterance that names an actual date or asks for a span, so the two never
/// compete for the same phrasing.
class DateSkill extends Skill {
  // ignore: prefer_initializing_formals
  const DateSkill({DateTime Function()? clock}) : _clock = clock;

  final DateTime Function()? _clock;
  DateTime get _now => (_clock ?? DateTime.now)();

  @override
  String get name => 'dates';

  @override
  String get description => 'Days between dates, countdowns, and ages';

  @override
  List<String> get examples => const [
        'days between 1 jan 2026 and 15 aug 2026',
        'how many days until 25 december',
        'how old am i if i was born 12 march 1998',
        '90 days after 1 march 2026',
      ];

  static final _between = RegExp(
    r'days?\s+(?:between|from)\s+(.+?)\s+(?:and|to)\s+(.+)',
  );
  /// Hinglish: "1 jan se 15 aug tak kitne din" — the span comes first and the
  /// question word last, so the English pattern cannot match it.
  static final _betweenHinglish = RegExp(
    r'(.+?)\s+se\s+(.+?)\s+tak\s+(?:kitne\s+)?din',
  );
  static final _until = RegExp(
    r'(?:how\s+many\s+)?days?\s+(?:until|till|to|before)\s+(.+)',
  );
  static final _since = RegExp(
    r'(?:how\s+many\s+)?days?\s+(?:since|after|from)\s+(.+)',
  );
  static final _born = RegExp(
    r'born\s+(?:on\s+)?(.+)',
  );
  static final _shift = RegExp(
    r'(\d+)\s+days?\s+(after|before)\s+(.+)',
  );

  @override
  double score(Utterance u) {
    final t = u.text;
    if (_shift.hasMatch(t) && _hasDate(_shift.firstMatch(t)!.group(3)!)) {
      return 0.95;
    }
    final span = _between.firstMatch(t) ?? _betweenHinglish.firstMatch(t);
    if (span != null &&
        _hasDate(span.group(1)!) &&
        _hasDate(span.group(2)!)) {
      return 0.96;
    }
    if (u.hasAny(const ['how old', 'age']) && _born.hasMatch(t)) return 0.95;
    if (_born.hasMatch(t) && _hasDate(_born.firstMatch(t)!.group(1)!)) {
      return 0.9;
    }
    if (_until.hasMatch(t) && _hasDate(_until.firstMatch(t)!.group(1)!)) {
      return 0.94;
    }
    if (_since.hasMatch(t) && _hasDate(_since.firstMatch(t)!.group(1)!)) {
      return 0.94;
    }
    return 0;
  }

  @override
  SkillReply run(Utterance u) {
    final t = u.text;
    final now = _now;

    final shift = _shift.firstMatch(t);
    if (shift != null) {
      final n = int.parse(shift.group(1)!);
      final forward = shift.group(2) == 'after';
      final base = _date(shift.group(3)!, now);
      if (base == null) return _unreadable(shift.group(3)!);
      final out = forward
          ? base.add(Duration(days: n))
          : base.subtract(Duration(days: n));
      return SkillReply(
        '${formatDay(out)}, ${formatDate(out)}',
        detail: '$n days ${shift.group(2)} ${formatDate(base)}',
      );
    }

    final between = _between.firstMatch(t) ?? _betweenHinglish.firstMatch(t);
    if (between != null) {
      final a = _date(between.group(1)!, now);
      final b = _date(between.group(2)!, now);
      if (a == null) return _unreadable(between.group(1)!);
      if (b == null) return _unreadable(between.group(2)!);
      final days = daysBetween(a, b).abs();
      return SkillReply(
        '$days ${days == 1 ? 'day' : 'days'}',
        detail: '${formatDate(a)} to ${formatDate(b)} · ${_inWeeks(days)}',
      );
    }

    // Age must be checked before the generic "days since", since "born on X"
    // also reads as a span from a past date.
    final born = _born.firstMatch(t);
    if (born != null) {
      final dob = _date(born.group(1)!, now);
      if (dob == null) return _unreadable(born.group(1)!);
      if (dob.isAfter(now)) {
        return const SkillReply('That birth date is in the future.');
      }
      return SkillReply(
        _age(dob, now),
        detail: 'born ${formatDay(dob)}, ${formatDate(dob)} · '
            '${daysBetween(dob, now)} days',
      );
    }

    final until = _until.firstMatch(t);
    if (until != null) {
      final target = _nextOccurrence(until.group(1)!, now);
      if (target == null) return _unreadable(until.group(1)!);
      final days = daysBetween(now, target);
      if (days == 0) return SkillReply('That is today — ${formatDate(target)}');
      if (days < 0) {
        return SkillReply(
          '${days.abs()} days ago',
          detail: '${formatDate(target)} has already passed',
        );
      }
      return SkillReply(
        '$days ${days == 1 ? 'day' : 'days'}',
        detail: 'until ${formatDay(target)}, ${formatDate(target)} · '
            '${_inWeeks(days)}',
      );
    }

    final since = _since.firstMatch(t);
    if (since != null) {
      final from = _date(since.group(1)!, now);
      if (from == null) return _unreadable(since.group(1)!);
      final days = daysBetween(from, now);
      return SkillReply(
        '${days.abs()} ${days.abs() == 1 ? 'day' : 'days'}',
        detail: '${days < 0 ? 'until' : 'since'} ${formatDate(from)}',
      );
    }

    return const SkillReply("I couldn't find a date in that.");
  }

  bool _hasDate(String s) => parseDate(s.trim(), now: _now) != null;

  DateTime? _date(String s, DateTime now) => parseDate(s.trim(), now: now);

  /// For countdowns, a bare "25 december" means the *next* 25 December, not one
  /// that has already gone by this year.
  DateTime? _nextOccurrence(String s, DateTime now) {
    final d = _date(s, now);
    if (d == null) return null;
    final hadYear = RegExp(r'\d{4}|\d{2}\s*$').hasMatch(s.trim());
    if (hadYear) return d;
    if (daysBetween(now, d) >= 0) return d;
    return DateTime(d.year + 1, d.month, d.day);
  }

  String _age(DateTime dob, DateTime now) {
    var years = now.year - dob.year;
    var months = now.month - dob.month;
    var days = now.day - dob.day;

    if (days < 0) {
      months -= 1;
      // Days in the month that just ended, so a part-month is measured against
      // the right denominator (28, 30, or 31).
      days += DateTime(now.year, now.month, 0).day;
    }
    if (months < 0) {
      years -= 1;
      months += 12;
    }

    final parts = <String>[
      '$years ${years == 1 ? 'year' : 'years'}',
      if (months > 0) '$months ${months == 1 ? 'month' : 'months'}',
      if (days > 0) '$days ${days == 1 ? 'day' : 'days'}',
    ];
    return parts.join(', ');
  }

  String _inWeeks(int days) {
    final weeks = days ~/ 7;
    final rest = days % 7;
    if (weeks == 0) return '$days ${days == 1 ? 'day' : 'days'}';
    if (rest == 0) return '$weeks ${weeks == 1 ? 'week' : 'weeks'}';
    return '$weeks ${weeks == 1 ? 'week' : 'weeks'} '
        '$rest ${rest == 1 ? 'day' : 'days'}';
  }

  SkillReply _unreadable(String s) =>
      SkillReply('I couldn\'t read "${s.trim()}" as a date.');
}
