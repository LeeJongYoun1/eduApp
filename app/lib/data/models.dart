import '../format.dart';

class School {
  const School({required this.id, required this.name, required this.sido, this.sigungu});
  final int id;
  final String name;
  final String sido;
  final String? sigungu;

  factory School.fromJson(Map<String, dynamic> j) =>
      School(id: j['id'] as int, name: j['name'] as String, sido: j['sido'] as String, sigungu: j['sigungu'] as String?);
}

class Child {
  const Child({required this.id, required this.nickname, required this.grade, required this.school});
  final int id;
  final String nickname;
  final int grade;
  final School school;

  factory Child.fromJson(Map<String, dynamic> j) => Child(
        id: j['id'] as int,
        nickname: j['nickname'] as String,
        grade: j['grade'] as int,
        school: School.fromJson(j['school'] as Map<String, dynamic>),
      );
}

/// 관심 지역. sigungu == '' 이면 시도 전체.
class Region {
  const Region(this.sido, this.sigungu);
  final String sido;
  final String sigungu;

  @override
  bool operator ==(Object other) => other is Region && other.sido == sido && other.sigungu == sigungu;
  @override
  int get hashCode => Object.hash(sido, sigungu);
  @override
  String toString() => sigungu.isEmpty ? '$sido 전체' : '$sido $sigungu';
}

class ProgramItem {
  const ProgramItem({
    required this.id,
    required this.title,
    required this.institutionName,
    required this.url,
    this.description,
    this.fee,
    this.gradeMin,
    this.gradeMax,
    this.startsOn,
    this.endsOn,
    this.applyStartsAt,
    this.applyEndsAt,
  });
  final int id;
  final String title;
  final String institutionName;
  final String url;
  final String? description;
  final String? fee;
  final int? gradeMin;
  final int? gradeMax;
  final DateTime? startsOn;
  final DateTime? endsOn;
  final DateTime? applyStartsAt;
  final DateTime? applyEndsAt;

  factory ProgramItem.fromJson(Map<String, dynamic> j) {
    DateTime? day(Object? v) => v == null ? null : DateTime.parse(v as String);
    DateTime? at(Object? v) => v == null ? null : kst(DateTime.parse(v as String));
    return ProgramItem(
      id: j['id'] as int,
      title: j['title'] as String,
      institutionName: j['institution_name'] as String,
      url: j['url'] as String,
      description: j['description'] as String?,
      fee: j['fee'] as String?,
      gradeMin: j['grade_min'] as int?,
      gradeMax: j['grade_max'] as int?,
      startsOn: day(j['starts_on']),
      endsOn: day(j['ends_on']),
      applyStartsAt: at(j['apply_starts_at']),
      applyEndsAt: at(j['apply_ends_at']),
    );
  }
}
