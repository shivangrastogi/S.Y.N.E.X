/// A small arithmetic evaluator.
///
/// Deliberately not `dart:mirrors`, not an eval, not a dependency: the phone
/// tier has to answer instantly and offline, and the grammar a person actually
/// speaks at an assistant is tiny — four operations, powers, and parentheses.
library;

import 'dart:math' as math;

class ExprException implements Exception {
  const ExprException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Evaluates [src], throwing [ExprException] on anything malformed.
double evaluateExpression(String src) {
  final tokens = _tokenise(src);
  if (tokens.isEmpty) throw const ExprException('nothing to calculate');
  final parser = _Parser(tokens);
  final value = parser.parseExpr();
  parser.expectEnd();
  return value;
}

/// True when [src] looks like arithmetic — used by the maths skill to decide
/// whether to claim an utterance, without paying for a full parse.
bool looksLikeExpression(String src) {
  if (!RegExp(r'\d').hasMatch(src)) return false;
  if (!RegExp(r'[+\-*/^x×÷]').hasMatch(src)) return false;
  // Reject things that are mostly words with a stray hyphen: "re-run 2 tests".
  final letters = RegExp(r'[a-z]', caseSensitive: false).allMatches(src).length;
  return letters <= 2;
}

// ---------------------------------------------------------------- tokeniser

sealed class _Tok {
  const _Tok();
}

class _Num extends _Tok {
  const _Num(this.value);
  final double value;
}

class _Op extends _Tok {
  const _Op(this.symbol);
  final String symbol;
}

List<_Tok> _tokenise(String src) {
  final out = <_Tok>[];
  final s = src.trim();
  var i = 0;

  while (i < s.length) {
    final c = s[i];

    if (c == ' ' || c == ',' || c == '_') {
      i++;
      continue;
    }

    if (_isDigit(c) || (c == '.' && i + 1 < s.length && _isDigit(s[i + 1]))) {
      final start = i;
      var seenDot = false;
      while (i < s.length) {
        final d = s[i];
        if (_isDigit(d)) {
          i++;
        } else if (d == '.' && !seenDot) {
          seenDot = true;
          i++;
        } else if (d == ',' && i + 1 < s.length && _isDigit(s[i + 1])) {
          i++; // thousands separator inside a number
        } else {
          break;
        }
      }
      final raw = s.substring(start, i).replaceAll(',', '');
      final v = double.tryParse(raw);
      if (v == null) throw ExprException('cannot read the number "$raw"');
      out.add(_Num(v));
      continue;
    }

    switch (c) {
      case '+':
      case '-':
      case '(':
      case ')':
      case '^':
        out.add(_Op(c));
        i++;
      case '*':
      case 'x':
      case 'X':
      case '×': // ×
        out.add(const _Op('*'));
        i++;
      case '/':
      case '÷': // ÷
        out.add(const _Op('/'));
        i++;
      default:
        throw ExprException('"$c" is not something I can calculate');
    }
  }
  return out;
}

bool _isDigit(String c) => c.codeUnitAt(0) >= 0x30 && c.codeUnitAt(0) <= 0x39;

// ------------------------------------------------------------------ parser

class _Parser {
  _Parser(this._toks);
  final List<_Tok> _toks;
  int _i = 0;

  _Tok? get _peek => _i < _toks.length ? _toks[_i] : null;

  bool _atOp(String symbol) {
    final t = _peek;
    return t is _Op && t.symbol == symbol;
  }

  void expectEnd() {
    if (_i != _toks.length) {
      throw const ExprException('there is something extra at the end');
    }
  }

  /// expr := term (('+' | '-') term)*
  double parseExpr() {
    var left = _parseTerm();
    while (_atOp('+') || _atOp('-')) {
      final op = (_toks[_i] as _Op).symbol;
      _i++;
      final right = _parseTerm();
      left = op == '+' ? left + right : left - right;
    }
    return left;
  }

  /// term := unary (('*' | '/') unary | '(' expr ')')*
  double _parseTerm() {
    var left = _parseUnary();
    while (true) {
      if (_atOp('*') || _atOp('/')) {
        final op = (_toks[_i] as _Op).symbol;
        _i++;
        final right = _parseUnary();
        if (op == '/') {
          if (right == 0) throw const ExprException('cannot divide by zero');
          left = left / right;
        } else {
          left = left * right;
        }
      } else if (_atOp('(')) {
        // Implicit multiplication: 3(4+1). Only before a bracket, so "2 3"
        // stays an error rather than quietly becoming 6.
        left = left * _parseUnary();
      } else {
        return left;
      }
    }
  }

  /// unary := ('-' | '+') unary | power
  double _parseUnary() {
    if (_atOp('-')) {
      _i++;
      return -_parseUnary();
    }
    if (_atOp('+')) {
      _i++;
      return _parseUnary();
    }
    return _parsePower();
  }

  /// power := primary ('^' unary)?  — right-associative, binds tighter than
  /// unary minus so -2^2 is -4, as in ordinary maths notation.
  double _parsePower() {
    final base = _parsePrimary();
    if (_atOp('^')) {
      _i++;
      final exp = _parseUnary();
      final r = _pow(base, exp);
      if (r.isNaN || r.isInfinite) {
        throw const ExprException('that power is too large to work out');
      }
      return r;
    }
    return base;
  }

  double _parsePrimary() {
    final t = _peek;
    if (t == null) throw const ExprException('the expression stops early');

    if (t is _Num) {
      _i++;
      return t.value;
    }
    if (t is _Op && t.symbol == '(') {
      _i++;
      final v = parseExpr();
      if (!_atOp(')')) throw const ExprException('a bracket is not closed');
      _i++;
      return v;
    }
    throw ExprException('"${(t as _Op).symbol}" is out of place');
  }

  static double _pow(double a, double b) {
    // Catch "10^400" before it silently becomes Infinity.
    if (b.abs() > 308 && a.abs() > 1) return double.infinity;
    return math.pow(a, b).toDouble();
  }
}
