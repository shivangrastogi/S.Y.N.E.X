import '../skill.dart';
import '../utterance.dart';

/// String operations that are instant on-device and pointless to send anywhere.
class TextSkill extends Skill {
  const TextSkill();

  @override
  String get name => 'text';

  @override
  String get description => 'Reverse, count, and re-case text';

  @override
  List<String> get examples => const [
        'reverse stressed',
        'count words in this sentence',
        'uppercase hello world',
        'how many characters in supercalifragilistic',
      ];

  static const _reverse = ['reverse ', 'ulta karo ', 'palat '];
  static const _upper = ['uppercase ', 'upper case ', 'capitalise ', 'capitalize '];
  static const _lower = ['lowercase ', 'lower case '];

  static final _countWords = RegExp(r'(?:count|how many)\s+words?\s+(?:in|of)\s+(.+)');
  static final _countChars =
      RegExp(r'(?:count|how many)\s+(?:characters?|letters?|chars?)\s+(?:in|of)\s+(.+)');

  @override
  double score(Utterance u) {
    if (_countWords.hasMatch(u.text) || _countChars.hasMatch(u.text)) return 0.9;
    for (final p in [..._reverse, ..._upper, ..._lower]) {
      if (u.text.startsWith(p) && u.text.length > p.length) return 0.9;
    }
    return 0;
  }

  @override
  SkillReply run(Utterance u) {
    final chars = _countChars.firstMatch(u.text);
    if (chars != null) {
      final body = chars.group(1)!.trim();
      final n = body.replaceAll(' ', '').length;
      return SkillReply('$n characters', detail: '"$body", spaces not counted');
    }

    final words = _countWords.firstMatch(u.text);
    if (words != null) {
      final body = words.group(1)!.trim();
      final n = body.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).length;
      return SkillReply('$n ${n == 1 ? 'word' : 'words'}', detail: '"$body"');
    }

    for (final p in _reverse) {
      if (u.text.startsWith(p)) {
        final body = u.after(p);
        return SkillReply(String.fromCharCodes(body.runes.toList().reversed));
      }
    }
    for (final p in _upper) {
      if (u.text.startsWith(p)) return SkillReply(u.after(p).toUpperCase());
    }
    for (final p in _lower) {
      if (u.text.startsWith(p)) return SkillReply(u.after(p).toLowerCase());
    }

    return const SkillReply("I'm not sure what to do with that text.");
  }
}
