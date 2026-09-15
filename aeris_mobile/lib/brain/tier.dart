/// Where an answer came from.
///
/// This is the app's organising idea, not a debug detail: the user should
/// always be able to see whether A.E.R.I.S answered in their hand, reached the
/// laptop, or went out to the internet — because those three have very
/// different costs, latencies, and privacy properties.
enum Tier {
  /// Answered on the phone. No network, no laptop, no data leaves the device.
  device('on-device'),

  /// Answered by the laptop's full brain over the bridge.
  laptop('laptop'),

  /// Answered by a cloud model because the laptop was unreachable.
  cloud('cloud'),

  /// Nothing could answer.
  none('unanswered');

  const Tier(this.label);

  /// Lowercase, for the instrument readout under a reply.
  final String label;
}

/// A tier that can be asked a question.
abstract class TierHandler {
  Tier get tier;

  /// Whether this tier is worth trying right now — a paired-and-awake laptop,
  /// a live network. Cheap and synchronous; the router calls it per utterance.
  bool get isAvailable;

  /// Answers, or returns null to pass the utterance to the next tier.
  Future<String?> ask(String text);
}
