// 표시 형식. 모든 DateTime은 이미 KST 벽시계 값이라고 본다 (kst()로 변환).

const _weekdays = ['월', '화', '수', '목', '금', '토', '일'];

/// DB의 timestamptz → KST 벽시계 (기기 시간대 무시).
DateTime kst(DateTime t) => t.toUtc().add(const Duration(hours: 9));

String fmtDate(DateTime d, DateTime today) {
  final w = _weekdays[d.weekday - 1];
  return d.year == today.year ? '${d.month}/${d.day}($w)' : '${d.year}/${d.month}/${d.day}($w)';
}

String fmtTime(DateTime d) => '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';

String fmtPeriod(DateTime? start, DateTime? end, DateTime today) {
  if (start == null && end == null) return '기간 미정';
  if (start == null) return '~${fmtDate(end!, today)}';
  if (end == null || _sameDay(start, end)) return fmtDate(start, today);
  return '${fmtDate(start, today)}~${fmtDate(end, today)}';
}

String fmtGrades(int? min, int? max) {
  final lo = min ?? 1, hi = max ?? 6;
  if (lo <= 1 && hi >= 6) return '초등 전체';
  return lo == hi ? '초$lo' : '초$lo~$hi';
}

String fmtApply(DateTime? startsAt, DateTime? endsAt, DateTime now) {
  String at(DateTime d) => '${fmtDate(d, now)} ${fmtTime(d)}';
  if (startsAt != null && startsAt.isAfter(now)) return '신청 ${at(startsAt)} 시작';
  if (endsAt == null) return startsAt == null ? '신청 기간은 기관 페이지에서 확인해요' : '신청 중';
  return startsAt == null ? '신청 마감 ${at(endsAt)}' : '신청 중 · ${at(endsAt)} 마감';
}

/// 마감이 앞으로 72시간 안이면 "마감 임박".
bool closingSoon(DateTime? endsAt, DateTime now) =>
    endsAt != null && endsAt.isAfter(now) && endsAt.difference(now) <= const Duration(hours: 72);

/// 이번 주말(토~일). 일요일이면 그날 하루.
(DateTime, DateTime) thisWeekend(DateTime today) {
  final d = DateTime(today.year, today.month, today.day);
  if (d.weekday == DateTime.sunday) return (d, d);
  final sat = d.add(Duration(days: DateTime.saturday - d.weekday));
  return (sat, sat.add(const Duration(days: 1)));
}

bool _sameDay(DateTime a, DateTime b) => a.year == b.year && a.month == b.month && a.day == b.day;
