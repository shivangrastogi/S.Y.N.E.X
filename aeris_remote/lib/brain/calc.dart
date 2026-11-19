// Spoken arithmetic for the brain's `calculate` tool: "25 into 4",
// "15 percent of 200", "100 divided by 8 plus 3", "(2+3)*4", "50 ka 20
// percent". Precedence-correct (shunting-yard), no eval, no dependencies.

/// The value of a spoken [expression], or null if it isn't arithmetic.
double? calculate(String expression) {
  var s = ' ${expression.toLowerCase()} ';
  // "50 ka 20 percent" → "20 percent of 50"
  s = s.replaceAllMapped(
      RegExp(r'(\d+(?:\.\d+)?)\s+(?:ka|ki|ke)\s+(\d+(?:\.\d+)?)\s*(?:percent|pratishat|%)'),
      (m) => ' ${m[2]} % ${m[1]} ');
  const words = <String, String>{
    'multiplied by': '*', 'divided by': '/', 'percent of': '%', 'into': '*',
    'times': '*', 'guna': '*', 'x': '*', 'multiply': '*', 'plus': '+',
    'jama': '+', 'aur': '+', 'add': '+', 'minus': '-', 'ghata': '-',
    'less': '-', 'by': '/', 'bhaag': '/', 'divide': '/', 'over': '/',
    'percent': '%', 'pratishat': '%', 'of': '', 'ka': '', 'ki': '', 'ke': '',
    'what is': '', "what's": '', 'kitna': '', 'hota': '', 'hai': '',
    'equals': '', 'calculate': '',
  };
  for (final e in words.entries) {
    s = s.replaceAll(RegExp('(?<![a-z])${RegExp.escape(e.key)}(?![a-z])'), ' ${e.value} ');
  }
  s = s.replaceAll('×', '*').replaceAll('÷', '/').replaceAll(',', '');
  final tokens = RegExp(r'\d+(?:\.\d+)?|[-+*/%()]|\S').allMatches(s).map((m) => m[0]!).toList();
  if (tokens.isEmpty || tokens.any((t) => !RegExp(r'^(\d+(\.\d+)?|[-+*/%()])$').hasMatch(t))) {
    return null;
  }
  if (!tokens.any((t) => '+-*/%'.contains(t) && t.isNotEmpty)) return null;

  // Shunting-yard. '%' is binary "a percent of b" = a / 100 * b.
  const prec = {'+': 1, '-': 1, '*': 2, '/': 2, '%': 2, 'neg': 3};
  final out = <String>[], ops = <String>[];
  String? prev;
  for (final t in tokens) {
    if (RegExp(r'^\d').hasMatch(t)) {
      out.add(t);
    } else if (t == '(') {
      ops.add(t);
    } else if (t == ')') {
      while (ops.isNotEmpty && ops.last != '(') {
        out.add(ops.removeLast());
      }
      if (ops.isEmpty) return null;
      ops.removeLast();
    } else {
      final unary = t == '-' && (prev == null || '+-*/%('.contains(prev));
      final op = unary ? 'neg' : t;
      while (!unary && ops.isNotEmpty && ops.last != '(' && prec[ops.last]! >= prec[op]!) {
        out.add(ops.removeLast());
      }
      ops.add(op);
    }
    prev = t;
  }
  while (ops.isNotEmpty) {
    final op = ops.removeLast();
    if (op == '(') return null;
    out.add(op);
  }
  final st = <double>[];
  for (final t in out) {
    if (RegExp(r'^\d').hasMatch(t)) {
      st.add(double.parse(t));
    } else if (t == 'neg') {
      if (st.isEmpty) return null;
      st.add(-st.removeLast());
    } else {
      if (st.length < 2) return null;
      final b = st.removeLast(), a = st.removeLast();
      st.add(switch (t) {
        '+' => a + b,
        '-' => a - b,
        '*' => a * b,
        '/' => a / b,
        _ => a / 100 * b,
      });
    }
  }
  return st.length == 1 && st.single.isFinite ? st.single : null;
}

/// 12 → "12", 2.5 → "2.5", 1/3 → "0.33".
String prettyNumber(double v) {
  if (v == v.roundToDouble() && v.abs() < 1e15) return v.toInt().toString();
  final s = v.toStringAsFixed(2);
  return s.replaceFirst(RegExp(r'0+$'), '').replaceFirst(RegExp(r'\.$'), '');
}
