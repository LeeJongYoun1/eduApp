import 'package:eduapp/data/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('ProgramItem.fromJson converts times to KST and dates', () {
    final p = ProgramItem.fromJson({
      'id': 3,
      'title': '공간 오감',
      'institution_name': '국립중앙박물관',
      'url': 'https://www.museum.go.kr/x',
      'description': null,
      'fee': null,
      'grade_min': 3,
      'grade_max': null,
      'starts_on': '2026-11-07',
      'ends_on': null,
      'apply_starts_at': null,
      'apply_ends_at': '2026-11-26T14:59:00+00:00',
    });
    expect(p.institutionName, '국립중앙박물관');
    expect(p.startsOn, DateTime(2026, 11, 7));
    expect(p.endsOn, isNull);
    expect(p.applyStartsAt, isNull);
    expect((p.applyEndsAt!.day, p.applyEndsAt!.hour, p.applyEndsAt!.minute), (26, 23, 59));
    expect(p.gradeMin, 3);
    expect(p.gradeMax, isNull);
  });

  test('Child.fromJson reads nested school', () {
    final c = Child.fromJson({
      'id': 1,
      'nickname': '서준',
      'grade': 4,
      'school': {'id': 9, 'name': '분당초등학교', 'sido': '경기', 'sigungu': '성남시'},
    });
    expect(c.school.name, '분당초등학교');
    expect(c.school.id, 9);
    expect(c.grade, 4);
  });

  test('Region equality', () {
    expect(const Region('서울', ''), const Region('서울', ''));
    const a = Region('서울', ''), b = Region('서울', '');
    expect((<Region>{}..add(a)..add(b)).length, 1);
    expect(const Region('서울', '') == const Region('서울', '용산구'), isFalse);
  });
}
