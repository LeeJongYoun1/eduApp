import 'package:eduapp/format.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final today = DateTime(2026, 11, 6); // 금요일
  final now = DateTime(2026, 11, 6, 20);

  test('fmtDate', () {
    expect(fmtDate(DateTime(2026, 11, 8), today), '11/8(일)');
    expect(fmtDate(DateTime(2027, 1, 5), today), '2027/1/5(화)');
  });

  test('fmtTime', () {
    expect(fmtTime(DateTime(2026, 11, 10, 9, 5)), '09:05');
  });

  test('fmtPeriod', () {
    expect(fmtPeriod(DateTime(2026, 11, 7), DateTime(2026, 11, 7), today), '11/7(토)');
    expect(fmtPeriod(DateTime(2026, 11, 7), DateTime(2026, 12, 12), today), '11/7(토)~12/12(토)');
    expect(fmtPeriod(null, null, today), '기간 미정');
    expect(fmtPeriod(null, DateTime(2026, 11, 20), today), '~11/20(금)');
  });

  test('fmtGrades', () {
    expect(fmtGrades(3, 6), '초3~6');
    expect(fmtGrades(4, 4), '초4');
    expect(fmtGrades(1, 6), '초등 전체');
    expect(fmtGrades(null, null), '초등 전체');
  });

  test('fmtApply', () {
    expect(fmtApply(null, DateTime(2026, 11, 26, 23, 59), now), '신청 마감 11/26(목) 23:59');
    expect(fmtApply(DateTime(2026, 11, 10, 10), DateTime(2026, 11, 20, 18), now), '신청 11/10(화) 10:00 시작');
    expect(fmtApply(DateTime(2026, 11, 1, 10), DateTime(2026, 11, 20, 18), now), '신청 중 · 11/20(금) 18:00 마감');
  });

  test('closingSoon', () {
    expect(closingSoon(DateTime(2026, 11, 8, 18), now), isTrue);
    expect(closingSoon(DateTime(2026, 11, 10, 21), now), isFalse);
    expect(closingSoon(DateTime(2026, 11, 5), now), isFalse);
    expect(closingSoon(null, now), isFalse);
  });

  test('thisWeekend', () {
    expect(thisWeekend(DateTime(2026, 11, 6)), (DateTime(2026, 11, 7), DateTime(2026, 11, 8)));
    expect(thisWeekend(DateTime(2026, 11, 7)), (DateTime(2026, 11, 7), DateTime(2026, 11, 8)));
    expect(thisWeekend(DateTime(2026, 11, 8)), (DateTime(2026, 11, 8), DateTime(2026, 11, 8)));
  });

  test('kst', () {
    final t = kst(DateTime.utc(2026, 11, 26, 14, 59));
    expect((t.day, t.hour, t.minute), (26, 23, 59));
  });
}
