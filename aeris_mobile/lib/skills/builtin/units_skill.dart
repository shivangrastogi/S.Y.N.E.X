import '../../core/num_format.dart';
import '../skill.dart';
import '../utterance.dart';

class _Unit {
  const _Unit(this.canonical, this.dimension, this.toBase, {this.offset = 0});

  final String canonical;
  final String dimension;

  /// Multiply by this to reach the dimension's base unit.
  final double toBase;

  /// Added *after* scaling — only temperature needs it.
  final double offset;
}

/// Unit conversion for the units that actually come up: distance, mass,
/// volume, temperature, and data size.
class UnitsSkill extends Skill {
  const UnitsSkill();

  @override
  String get name => 'units';

  @override
  String get description => 'Convert between units without a network round trip';

  @override
  List<String> get examples => const [
        '12 km in miles',
        '30 c to f',
        '2.5 kg in pounds',
        '500 ml to cups',
      ];

  // Base units: metre, gram, litre, celsius, byte.
  static const Map<String, _Unit> _units = {
    // distance (base: metre)
    'm': _Unit('metres', 'distance', 1),
    'metre': _Unit('metres', 'distance', 1),
    'metres': _Unit('metres', 'distance', 1),
    'meter': _Unit('metres', 'distance', 1),
    'meters': _Unit('metres', 'distance', 1),
    'km': _Unit('kilometres', 'distance', 1000),
    'kilometre': _Unit('kilometres', 'distance', 1000),
    'kilometres': _Unit('kilometres', 'distance', 1000),
    'kilometer': _Unit('kilometres', 'distance', 1000),
    'kilometers': _Unit('kilometres', 'distance', 1000),
    'cm': _Unit('centimetres', 'distance', 0.01),
    'mm': _Unit('millimetres', 'distance', 0.001),
    'mile': _Unit('miles', 'distance', 1609.344),
    'miles': _Unit('miles', 'distance', 1609.344),
    'mi': _Unit('miles', 'distance', 1609.344),
    'foot': _Unit('feet', 'distance', 0.3048),
    'feet': _Unit('feet', 'distance', 0.3048),
    'ft': _Unit('feet', 'distance', 0.3048),
    'inch': _Unit('inches', 'distance', 0.0254),
    'inches': _Unit('inches', 'distance', 0.0254),
    'in': _Unit('inches', 'distance', 0.0254),
    'yard': _Unit('yards', 'distance', 0.9144),
    'yards': _Unit('yards', 'distance', 0.9144),

    // mass (base: gram)
    'g': _Unit('grams', 'mass', 1),
    'gram': _Unit('grams', 'mass', 1),
    'grams': _Unit('grams', 'mass', 1),
    'kg': _Unit('kilograms', 'mass', 1000),
    'kilo': _Unit('kilograms', 'mass', 1000),
    'kilos': _Unit('kilograms', 'mass', 1000),
    'kilogram': _Unit('kilograms', 'mass', 1000),
    'kilograms': _Unit('kilograms', 'mass', 1000),
    'mg': _Unit('milligrams', 'mass', 0.001),
    'lb': _Unit('pounds', 'mass', 453.59237),
    'lbs': _Unit('pounds', 'mass', 453.59237),
    'pound': _Unit('pounds', 'mass', 453.59237),
    'pounds': _Unit('pounds', 'mass', 453.59237),
    'oz': _Unit('ounces', 'mass', 28.349523125),
    'ounce': _Unit('ounces', 'mass', 28.349523125),
    'ounces': _Unit('ounces', 'mass', 28.349523125),

    // volume (base: litre)
    'l': _Unit('litres', 'volume', 1),
    'litre': _Unit('litres', 'volume', 1),
    'litres': _Unit('litres', 'volume', 1),
    'liter': _Unit('litres', 'volume', 1),
    'liters': _Unit('litres', 'volume', 1),
    'ml': _Unit('millilitres', 'volume', 0.001),
    'cup': _Unit('cups', 'volume', 0.2365882365),
    'cups': _Unit('cups', 'volume', 0.2365882365),
    'gallon': _Unit('gallons', 'volume', 3.785411784),
    'gallons': _Unit('gallons', 'volume', 3.785411784),

    // temperature (base: celsius)
    'c': _Unit('°C', 'temp', 1),
    'celsius': _Unit('°C', 'temp', 1),
    'centigrade': _Unit('°C', 'temp', 1),
    'f': _Unit('°F', 'temp', 5 / 9, offset: -32 * 5 / 9),
    'fahrenheit': _Unit('°F', 'temp', 5 / 9, offset: -32 * 5 / 9),
    'k': _Unit('K', 'temp', 1, offset: -273.15),
    'kelvin': _Unit('K', 'temp', 1, offset: -273.15),

    // data (base: byte)
    'kb': _Unit('KB', 'data', 1024),
    'mb': _Unit('MB', 'data', 1024 * 1024),
    'gb': _Unit('GB', 'data', 1024 * 1024 * 1024),
    'tb': _Unit('TB', 'data', 1024.0 * 1024 * 1024 * 1024),
  };

  /// `ko` covers the Hinglish word order: "12 km ko miles me badlo". The
  /// pattern is unanchored, so the trailing verb is simply ignored.
  static final _pattern = RegExp(
    r'(-?[\d.,]+)\s*([a-z°]+)\s*(?:in|to|into|me|mein|ko)\s+([a-z°]+)',
  );

  @override
  double score(Utterance u) {
    final m = _pattern.firstMatch(u.text);
    if (m == null) return 0;
    final from = _units[m.group(2)!];
    final to = _units[m.group(3)!];
    if (from == null || to == null) return 0;
    return from.dimension == to.dimension ? 0.95 : 0.6;
  }

  /// "12 km in miles" then "and in feet?" -> "12 km in feet".
  @override
  String? followUp(Utterance previous, Utterance current) {
    final prev = _pattern.firstMatch(previous.text);
    if (prev == null) return null;
    final target = _bareUnit(current.text);
    if (target == null) return null;
    return '${prev.group(1)} ${prev.group(2)} in $target';
  }

  /// A follow-up must be nothing but a unit, once the connective words are
  /// stripped — otherwise "and how far is the moon" would look like one.
  static String? _bareUnit(String s) {
    var t = s
        .replaceFirst(
            RegExp(r'^(?:and|aur|what about|how about|ok|okay)\s+'), '')
        .replaceFirst(RegExp(r'^(?:in|to|into|me|mein)\s+'), '')
        .replaceAll(RegExp(r'[?.!]'), '')
        .trim();
    if (t.isEmpty || t.contains(' ')) return null;
    return _units.containsKey(t) ? t : null;
  }

  @override
  SkillReply run(Utterance u) {
    final m = _pattern.firstMatch(u.text)!;
    final amount = double.parse(m.group(1)!.replaceAll(',', ''));
    final fromKey = m.group(2)!;
    final toKey = m.group(3)!;
    final from = _units[fromKey]!;
    final to = _units[toKey]!;

    if (from.dimension != to.dimension) {
      return SkillReply(
        "I can't convert ${from.canonical} to ${to.canonical} — "
        'those measure different things.',
      );
    }

    // to base, then out of base. Offsets are applied in base space so
    // temperature behaves (30°C -> 86°F, not 16.7).
    final base = amount * from.toBase + from.offset;
    final out = (base - to.offset) / to.toBase;

    final unitLabel = to.dimension == 'temp' ? to.canonical : ' ${to.canonical}';
    return SkillReply(
      '${groupThousands(formatNumber(out, maxDecimals: 4))}$unitLabel',
      detail: '${formatNumber(amount)} ${from.canonical} =',
    );
  }
}
