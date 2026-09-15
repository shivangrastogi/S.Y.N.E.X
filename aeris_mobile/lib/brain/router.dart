import '../core/logger.dart';
import '../skills/skill.dart';
import '../skills/utterance.dart';
import 'tier.dart';

/// What the router produced for one utterance.
class Answer {
  const Answer({
    required this.text,
    required this.tier,
    required this.elapsed,
    this.detail,
    this.skillName,
    this.tried = const [],
    this.resolvedAs,
  });

  final String text;
  final Tier tier;
  final Duration elapsed;

  /// Working shown under the answer, e.g. `15% of 2,400 =`.
  final String? detail;

  /// Which on-device skill answered, when [tier] is [Tier.device].
  final String? skillName;

  /// Tiers the router attempted before this one succeeded. Surfaced in the UI
  /// so a slow answer explains itself instead of just feeling slow.
  final List<Tier> tried;

  /// Set when an elliptical follow-up was expanded — "and in feet?" becomes
  /// "12 km in feet". Null for an utterance that stood on its own.
  final String? resolvedAs;

  bool get isAnswered => tier != Tier.none;
}

/// Routes an utterance down the tiers: phone, then laptop, then cloud.
///
/// The order is a deliberate product stance, not an optimisation. Answering on
/// the device is faster, works on a train, and keeps the utterance private —
/// so it is always tried first, and the remote tiers only ever see what the
/// phone genuinely could not handle.
class BrainRouter {
  BrainRouter({
    required this.skills,
    this.laptop,
    this.cloud,
  });

  final Skills skills;

  // Mutable: the laptop is paired and unpaired at runtime from settings, and
  // rebuilding the router would throw away the follow-up context with it.
  TierHandler? laptop;
  TierHandler? cloud;

  // The last thing answered on-device, for resolving follow-ups. Deliberately
  // only one turn deep: a longer memory makes stale rewrites more likely than
  // useful ones.
  Utterance? _lastUtterance;
  Skill? _lastSkill;

  /// Forgets the follow-up context — call when the transcript is cleared, so a
  /// new conversation cannot inherit the old one's subject.
  void resetContext() {
    _lastUtterance = null;
    _lastSkill = null;
  }

  /// Tiers in the order they will be tried, with their current reachability.
  /// The UI's status strip renders straight from this.
  Map<Tier, bool> get reach => {
        Tier.device: true, // always: it is the phone itself
        Tier.laptop: laptop?.isAvailable ?? false,
        Tier.cloud: cloud?.isAvailable ?? false,
      };

  Future<Answer> ask(String raw) async {
    final started = DateTime.now();
    final u = Utterance(raw);
    final tried = <Tier>[];

    if (u.isEmpty) {
      return Answer(
        text: 'Say that again?',
        tier: Tier.none,
        elapsed: DateTime.now().difference(started),
      );
    }

    // ---- tier 1: the phone ----
    tried.add(Tier.device);
    var effective = u;
    var skill = skills.select(u);

    // Nothing claimed it outright — try reading it as a follow-up to whatever
    // was answered last. Only the skill that answered gets asked, and only one
    // level deep, so a rewrite can never cascade.
    if (skill == null && _lastSkill != null && _lastUtterance != null) {
      final rewritten = _lastSkill!.followUp(_lastUtterance!, u);
      if (rewritten != null) {
        final expanded = Utterance(rewritten);
        final claimed = skills.select(expanded);
        if (claimed != null) {
          log.debug('router', 'follow-up: "${u.raw}" -> "$rewritten"');
          effective = expanded;
          skill = claimed;
        }
      }
    }

    if (skill != null) {
      final reply = await skills.handle(effective);
      if (reply != null) {
        _lastUtterance = effective;
        _lastSkill = skill;
        return Answer(
          text: reply.text,
          detail: reply.detail,
          tier: Tier.device,
          skillName: skill.name,
          elapsed: DateTime.now().difference(started),
          tried: tried,
          resolvedAs: identical(effective, u) ? null : effective.raw,
        );
      }
      // The skill matched but blew up; Skills.handle already logged it. Fall
      // through so the laptop still gets a chance at the utterance.
      log.warn('router', 'on-device skill ${skill.name} failed, falling through');
    }

    // ---- tier 2: the laptop ----
    for (final handler in [laptop, cloud]) {
      if (handler == null || !handler.isAvailable) continue;
      tried.add(handler.tier);
      try {
        final reply = await handler.ask(raw);
        if (reply != null && reply.trim().isNotEmpty) {
          return Answer(
            text: reply.trim(),
            tier: handler.tier,
            elapsed: DateTime.now().difference(started),
            tried: tried,
          );
        }
      } catch (e) {
        log.error('router', '${handler.tier.label} failed: $e');
      }
    }

    return Answer(
      text: _unansweredMessage(),
      tier: Tier.none,
      elapsed: DateTime.now().difference(started),
      tried: tried,
    );
  }

  /// The empty-handed case is a place to give direction, not to apologise.
  String _unansweredMessage() {
    final laptopUp = laptop?.isAvailable ?? false;
    final cloudUp = cloud?.isAvailable ?? false;
    if (!laptopUp && !cloudUp) {
      return "That one needs the laptop, and I can't reach it. "
          'Try a calculation, a conversion, or the time — those work offline.';
    }
    return "I don't have an answer for that yet.";
  }
}
