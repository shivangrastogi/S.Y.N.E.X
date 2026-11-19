import 'package:aeris_assistant/brain/parse.dart';
import 'package:aeris_assistant/brain/phone.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final evening = DateTime(2026, 11, 16, 21, 4);
  final morning = DateTime(2026, 11, 16, 8, 0);
  Clock? c(String s, [DateTime? now]) => parseClock(normalize(s), now ?? evening);

  group('parseClock', () {
    test('h:mm', () => expect(c('6:30 ka alarm', morning), const Clock(18, 30)));
    test('subah forces AM', () => expect(c('subah 6:30'), const Clock(6, 30)));
    test('shaam forces PM', () => expect(c('shaam 7 baje'), const Clock(19, 0)));
    test('raat 2 baje is 2 AM', () => expect(c('raat 2 baje'), const Clock(2, 0)));
    test('raat 10 baje is 10 PM', () => expect(c('raat 10 baje'), const Clock(22, 0)));
    test('kal 6 baje → morning', () => expect(c('kal 6 baje'), const Clock(6, 0)));
    test('saade 6 = 6:30', () => expect(c('subah saade 6'), const Clock(6, 30)));
    test('sava 7 = 7:15', () => expect(c('sava 7 baje subah'), const Clock(7, 15)));
    test('paune 8 = 7:45', () => expect(c('paune 8 baje subah'), const Clock(7, 45)));
    test('7 am', () => expect(c('alarm for 7 am'), const Clock(7, 0)));
    test('24h', () => expect(c('alarm 18:45'), const Clock(18, 45)));
    test('next occurrence: at 9 PM, "6 baje" means 6 AM', () => expect(c('6 baje'), const Clock(6, 0)));
    test('next occurrence: at 8 AM, "6 baje" means 6 PM', () => expect(c('6 baje', morning), const Clock(18, 0)));
    test('nothing', () => expect(c('alarm laga do'), isNull));
    test('written as a.m./p.m.', () {
      expect(const Clock(18, 5).spoken, '6:05 p.m.');
      expect(const Clock(6, 30).spoken, '6:30 a.m.');
      expect(const Clock(0, 15).spoken, '12:15 a.m.');
    });
  });

  group('parseDuration', () {
    test('minutes', () => expect(parseDuration(normalize('10 minute')), 600));
    test('seconds', () => expect(parseDuration(normalize('30 seconds')), 30));
    test('mixed', () => expect(parseDuration(normalize('1 ghanta 20 min')), 4800));
    test('aadha ghanta', () => expect(parseDuration(normalize('aadha ghanta')), 1800));
    test('hindi number word', () => expect(parseDuration(normalize('paanch minute')), 300));
    test('none', () => expect(parseDuration('timer lagao'), isNull));
  });

  group('parseMath', () {
    test('into', () => expect(parseMath('12 into 8')!.value, 96));
    test('plus', () => expect(parseMath('15 plus 7')!.value, 22));
    test('divide', () => expect(parseMath('100 divided by 4')!.value, 25));
    test('percent of', () => expect(parseMath('20 percent of 500')!.value, 100));
    test('hinglish percent', () => expect(parseMath('500 ka 20 percent')!.value, 100));
    test('format', () => expect(fmtNum(2.5), '2.5'));
  });

  group('contacts', () {
    final people = const [
      Person('Ravi Sharma', '98765 43210'),
      Person('Ravi Kumar', '91234 56789'),
      Person('Mummy', '99999 00000'),
      Person('Kavita', '90000 11111'),
    ];
    test('first-name match ranks first', () => expect(rankPeople(people, 'ravi').first.name, 'Ravi Sharma'));
    test('exact full name wins', () => expect(rankPeople(people, 'Ravi Kumar').first.name, 'Ravi Kumar'));
    test('honorific stripped', () => expect(rankPeople(people, 'mummy ji').first.name, 'Mummy'));
    test('no match', () => expect(rankPeople(people, 'zoya'), isEmpty));
    test('wa.me number', () => expect(waNumber('098765 43210'), '919876543210'));
  });
}
