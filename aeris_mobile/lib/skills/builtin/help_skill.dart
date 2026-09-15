import '../skill.dart';
import '../utterance.dart';

/// Answers "what can you do" from the live registry.
///
/// Discoverability is a real problem for an assistant: the empty state shows
/// one example per skill and then disappears for good after the first message.
/// This is the only way back to that list, and because it reads the registry
/// rather than a hand-written string, it cannot drift out of date.
class HelpSkill extends Skill {
  const HelpSkill(this._others);

  /// Supplied as a callback because the registry does not exist yet when this
  /// skill is constructed — see `defaultSkills()`.
  final List<Skill> Function() _others;

  /// Beyond this the reply stops being readable on a phone.
  static const int examplesPerSkill = 2;

  @override
  String get name => 'help';

  @override
  String get description => 'Lists what A.E.R.I.S can do on the phone';

  @override
  List<String> get examples => const ['what can you do'];

  @override
  double score(Utterance u) {
    if (u.hasAny(const [
      'what can you do',
      'what can i say',
      'what can i ask',
      'what do you do',
      'kya kar sakte ho',
      'kya kar sakti ho',
      'your skills',
      'list skills',
      'show commands',
    ])) {
      return 0.97;
    }
    // Bare "help" only — "help me split this bill" belongs to finance.
    if (u.text == 'help' || u.text == 'madad') return 0.95;
    return 0;
  }

  @override
  SkillReply run(Utterance u) {
    final others = _others().where((s) => s.name != name).toList()
      ..sort((a, b) => a.name.compareTo(b.name));

    final buf = StringBuffer();
    var total = 0;

    for (final s in others) {
      if (s.examples.isEmpty) continue;
      if (buf.isNotEmpty) buf.writeln();
      buf.writeln('${s.name.toUpperCase()} — ${s.description}');
      for (final ex in s.examples.take(examplesPerSkill)) {
        buf.writeln('  $ex');
      }
      total += s.examples.length;
    }

    if (buf.isEmpty) return const SkillReply('No skills are loaded.');

    return SkillReply(
      buf.toString().trimRight(),
      detail: '${others.length} skills on the phone · $total phrasings I know',
    );
  }
}
