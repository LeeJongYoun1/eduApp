import 'models.dart';

/// 앱의 모든 데이터 접근은 여기 한 곳으로 (API 서버로 옮길 때 이 구현만 바꾼다).
abstract class EduRepository {
  bool get signedIn;
  Future<void> signIn(String email, String password);
  Future<void> signUp(String email, String password);
  Future<void> signOut();
  Future<List<Child>> children();
  Future<void> saveChild({int? id, required String nickname, required int schoolId, required int grade});
  Future<void> deleteChild(int id);
  Future<List<School>> searchSchools(String query);
  Future<Set<Region>> regions();
  Future<void> saveRegions(Set<Region> regions);
  Future<List<ProgramItem>> programs({int? grade, DateTime? from, DateTime? to});
  Future<Set<int>> favoriteIds();
  Future<void> setFavorite(int programId, bool on);
  Future<List<SchoolTextbook>> schoolTextbooks(int childId);
  /// 학교 `is_holiday` 날(날짜만, 시각 없음) — from~to 포함.
  Future<Set<DateTime>> holidays(int schoolId, DateTime from, DateTime to);
  Future<void> correctPublisher(int childId, String subject, String publisher);
}
