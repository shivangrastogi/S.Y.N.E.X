/// Formats a computed number the way a person would write it.
///
/// `4.0` reads as "4", `2.5` stays "2.5", and long tails are cut at six
/// decimals rather than showing floating-point noise like `0.30000000000000004`.
String formatNumber(double v, {int maxDecimals = 6}) {
  if (v.isNaN) return 'not a number';
  if (v.isInfinite) return v.isNegative ? '-infinity' : 'infinity';

  // Integral values print without a decimal point, but only inside the range
  // where a double still represents integers exactly.
  if (v == v.roundToDouble() && v.abs() < 1e15) {
    return v.toStringAsFixed(0);
  }

  var s = v.toStringAsFixed(maxDecimals);
  if (s.contains('.')) {
    s = s.replaceFirst(RegExp(r'0+$'), '');
    s = s.replaceFirst(RegExp(r'\.$'), '');
  }
  return s;
}

/// Indian grouping: 1234567 -> "12,34,567". The last three digits group
/// together, then pairs. Used only where the answer is explicitly about lakhs
/// and crores — everywhere else stays on [groupThousands], since the app mixes
/// Hinglish speech with international units.
String groupIndian(String digits) {
  final neg = digits.startsWith('-');
  final body = neg ? digits.substring(1) : digits;
  final dot = body.indexOf('.');
  final intPart = dot < 0 ? body : body.substring(0, dot);
  final rest = dot < 0 ? '' : body.substring(dot);

  if (intPart.length <= 3) return '${neg ? '-' : ''}$intPart$rest';

  final last3 = intPart.substring(intPart.length - 3);
  var head = intPart.substring(0, intPart.length - 3);

  final chunks = <String>[];
  while (head.length > 2) {
    chunks.insert(0, head.substring(head.length - 2));
    head = head.substring(0, head.length - 2);
  }
  if (head.isNotEmpty) chunks.insert(0, head);

  return '${neg ? '-' : ''}${chunks.join(',')},$last3$rest';
}

/// Plain 3-digit grouping: 1234567 -> "1,234,567".
String groupThousands(String digits) {
  final neg = digits.startsWith('-');
  final body = neg ? digits.substring(1) : digits;
  final dot = body.indexOf('.');
  final intPart = dot < 0 ? body : body.substring(0, dot);
  final rest = dot < 0 ? '' : body.substring(dot);

  final buf = StringBuffer();
  for (var i = 0; i < intPart.length; i++) {
    if (i > 0 && (intPart.length - i) % 3 == 0) buf.write(',');
    buf.write(intPart[i]);
  }
  return '${neg ? '-' : ''}$buf$rest';
}
