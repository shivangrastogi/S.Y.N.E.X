import '../skill.dart';
import '../utterance.dart';

/// Clock and calendar questions, plus simple date arithmetic.
///
/// Takes its clock by injection so tests are not time-dependent.
class TimeSkill extends Skill {
  // The field is private and the parameter is not, so an initialising formal
  // cannot express this pairing.
  // ignore: prefer_initializing_formals
  const TimeSkill({DateTime Function()? clock}) : _clock = clock;

  final DateTime Function()? _clock;
  DateTime get _now => (_clock ?? DateTime.now)();

  @override
  String get name => 'time';

  @override
  String get description => 'The time, the date, and simple day arithmetic';

  @override
  List<String> get examples => const [
        'what time is it',
        'kya time hua hai',
        "today's date",
        'what day is it in 45 days',
      ];

  static const _months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  static const _days = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday',
    'Friday', 'Saturday', 'Sunday',
  ];

  static final _inDays = RegExp(r'in\s+(\d+)\s+days?');
  static final _agoDays = RegExp(r'(\d+)\s+days?\s+ago');

  @override
  double score(Utterance u) {
    final t = u.text;
    if (_inDays.hasMatch(t) || _agoDays.hasMatch(t)) {
      if (u.hasAny(const ['day', 'date', 'din', 'tarikh'])) return 0.9;
    }
    if (u.hasAny(const ['what time', 'kya time', 'time hua', 'time kya'])) {
      return 0.95;
    }
    if (u.hasAny(const ["today's date", 'todays date', 'what is the date',
        "what's the date", 'aaj ki tarikh', 'aaj ka din'])) {
      return 0.95;
    }
    if (u.hasAny(const ['what day is it', 'what day is today'])) return 0.9;
    return 0;
  }

  @override
  SkillReply run(Utterance u) {
    final now = _now;
    final t = u.text;

    final ahead = _inDays.firstMatch(t);
    if (ahead != null) {
      final n = int.parse(ahead.group(1)!);
      final then = now.add(Duration(days: n));
      return SkillReply(
        '${_dayName(then)}, ${_dateLine(then)}',
        detail: '$n days from today',
      );
    }

    final back = _agoDays.firstMatch(t);
    if (back != null) {
      final n = int.parse(back.group(1)!);
      final then = now.subtract(Duration(days: n));
      return SkillReply(
        '${_dayName(then)}, ${_dateLine(then)}',
        detail: '$n days ago',
      );
    }

    if (u.hasAny(const ['what time', 'kya time', 'time hua', 'time kya'])) {
      return SkillReply(_clockLine(now), detail: _dateLine(now));
    }

    return SkillReply(
      '${_dayName(now)}, ${_dateLine(now)}',
      detail: _clockLine(now),
    );
  }

  String _clockLine(DateTime d) {
    final h24 = d.hour;
    final h12 = h24 % 12 == 0 ? 12 : h24 % 12;
    final mm = d.minute.toString().padLeft(2, '0');
    return '$h12:$mm ${h24 < 12 ? 'am' : 'pm'}';
  }

  String _dateLine(DateTime d) => '${d.day} ${_months[d.month - 1]} ${d.year}';

  String _dayName(DateTime d) => _days[d.weekday - 1];
}
