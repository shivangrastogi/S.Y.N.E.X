import '../skill.dart';
import 'chance_skill.dart';
import 'date_skill.dart';
import 'finance_skill.dart';
import 'help_skill.dart';
import 'math_skill.dart';
import 'number_skill.dart';
import 'text_skill.dart';
import 'time_skill.dart';
import 'units_skill.dart';

/// Every skill that runs with no laptop, no network, and no permissions.
///
/// Ordering does not matter — [Skills.select] picks by confidence, not by
/// position — but keep the list alphabetical so additions are easy to spot.
Skills defaultSkills() {
  // HelpSkill reports on the registry it belongs to, so it takes a callback:
  // the registry does not exist yet at the moment the skill is constructed.
  late final Skills registry;
  registry = Skills([
    ChanceSkill(),
    const DateSkill(),
    const FinanceSkill(),
    HelpSkill(() => registry.all),
    const MathSkill(),
    const NumberSkill(),
    const TextSkill(),
    const TimeSkill(),
    const UnitsSkill(),
  ]);
  return registry;
}
