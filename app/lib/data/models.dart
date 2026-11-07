import '../format.dart';

/// 학교 교과서 정보 수집 상태 (schools.collect_status).
enum SchoolStatus {
  notRequested,
  pending,
  done,
  failed,
  notFound;

  /// 없거나 모르는 값은 notRequested.
  static SchoolStatus parse(Object? v) => switch (v) {
        'pending' => pending,
        'done' => done,
        'failed' => failed,
        'not_found' => notFound,
        _ => notRequested,
      };
}

class School {
  const School(
      {required this.id, required this.name, required this.sido, this.sigungu, this.status = SchoolStatus.notRequested});
  final int id;
  final String name;
  final String sido;
  final String? sigungu;
  final SchoolStatus status;

  factory School.fromJson(Map<String, dynamic> j) => School(
      id: j['id'] as int,
      name: j['name'] as String,
      sido: j['sido'] as String,
      sigungu: j['sigungu'] as String?,
      status: SchoolStatus.parse(j['collect_status']));
}

/// 한 과목의 출판사. publisher가 없으면 아직 모르는 과목.
class SchoolTextbook {
  const SchoolTextbook(
      {required this.subject, this.publisher, required this.confirmed, required this.isGuess, this.sourceUrl});
  final String subject;
  final String? publisher;
  final bool confirmed;
  final bool isGuess;
  final String? sourceUrl;

  factory SchoolTextbook.fromJson(Map<String, dynamic> j) => SchoolTextbook(
        subject: j['subject'] as String,
        publisher: j['publisher'] as String?,
        confirmed: j['confidence'] == 'confirmed',
        isGuess: j['is_guess'] as bool,
        sourceUrl: j['source_url'] as String?,
      );
}

/// 학교 평가계획에서 읽은 한 단원. month는 수업이 아니라 평가 월이다.
class ProgressItem {
  const ProgressItem({required this.subject, required this.standardCode, required this.unitTitle, required this.month});
  final String subject;
  final String standardCode;
  final String unitTitle;
  final int month;

  factory ProgressItem.fromJson(Map<String, dynamic> j) => ProgressItem(
        subject: j['subject'] as String,
        standardCode: j['standard_code'] as String,
        unitTitle: j['unit_title'] as String,
        month: j['month'] as int,
      );
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
