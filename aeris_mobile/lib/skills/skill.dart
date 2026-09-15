import 'dart:async';

import '../core/logger.dart';
import 'utterance.dart';

/// What a skill hands back when it handles an utterance.
class SkillReply {
  const SkillReply(this.text, {this.detail});

  /// The sentence the user reads (or hears).
  final String text;

  /// Optional working — shown in the transcript under the reply, e.g. the
  /// normalised expression a maths answer came from. Never spoken.
  final String? detail;
}

/// A thing A.E.R.I.S can do entirely on the phone.
///
/// Mirrors the laptop's `@skill` decorator in `core/skill_registry.py`: a name,
/// a description, and a handler. The difference is [score] — on the phone there
/// is no trained intent classifier to route with, so each skill states its own
/// confidence and the registry picks the winner.
abstract class Skill {
  const Skill();

  String get name;
  String get description;

  /// Example phrasings, shown in the app's "what can I say" surface. These are
  /// documentation, not routing — routing goes through [score].
  List<String> get examples => const [];

  /// Confidence that this skill should handle [u], from 0 to 1.
  ///
  /// Return 0 to decline. Anything at or above [Skills.threshold] is eligible;
  /// the highest score wins. Be honest here — an overconfident skill silently
  /// starves the laptop and cloud tiers of everything they are better at.
  double score(Utterance u);

  FutureOr<SkillReply> run(Utterance u);

  /// Expands an elliptical follow-up into a full utterance, or returns null to
  /// decline.
  ///
  /// Only ever called on the skill that answered [previous], because only that
  /// skill knows what "and in feet?" is missing. Keeping the knowledge here
  /// rather than in the router means a new skill brings its own follow-ups.
  String? followUp(Utterance previous, Utterance current) => null;
}

/// The on-device skill registry.
class Skills {
  Skills(this._skills);

  /// Below this, no skill is considered to have understood the utterance and
  /// the router falls through to the next tier.
  static const double threshold = 0.5;

  final List<Skill> _skills;

  List<Skill> get all => List.unmodifiable(_skills);

  /// Highest-scoring skill at or above [threshold], or null if none apply.
  Skill? select(Utterance u) {
    Skill? best;
    var bestScore = 0.0;
    for (final s in _skills) {
      final score = s.score(u);
      if (score > bestScore) {
        bestScore = score;
        best = s;
      }
    }
    if (best == null || bestScore < threshold) return null;
    log.debug('skills', 'selected ${best.name} (${bestScore.toStringAsFixed(2)})');
    return best;
  }

  /// Selects and runs in one step. Null means nothing on-device understood it.
  Future<SkillReply?> handle(Utterance u) async {
    final skill = select(u);
    if (skill == null) return null;
    try {
      return await skill.run(u);
    } catch (e) {
      log.error('skills', '${skill.name} threw: $e');
      // A crashing skill must not eat the utterance — let a later tier try.
      return null;
    }
  }
}
