import 'package:eduapp/data/models.dart';
import 'package:eduapp/data/repository.dart';

/// 화면 테스트용 메모리 repository. `failWith`를 넣으면 다음 호출 한 번이 그 예외를 던진다.
class FakeRepository implements EduRepository {
  FakeRepository({
    this.signedIn = false,
    List<Child>? children,
    List<School>? schools,
    Set<Region>? regions,
    List<ProgramItem>? programs,
    Set<int>? favorites,
  })  : childList = children ?? [],
        schoolList = schools ?? [],
        regionSet = regions ?? {},
        programList = programs ?? [],
        favorites = favorites ?? {};

  @override
  bool signedIn;
  List<Child> childList;
  List<School> schoolList;
  Set<Region> regionSet;
  List<ProgramItem> programList;
  Set<int> favorites;
  Object? failWith;
  final List<String> calls = [];

  Future<T> _call<T>(String name, T Function() body) async {
    calls.add(name);
    final f = failWith;
    if (f != null) {
      failWith = null;
      throw f;
    }
    return body();
  }

  @override
  Future<void> signIn(String email, String password) => _call('signIn($email)', () => signedIn = true);
  @override
  Future<void> signUp(String email, String password) => _call('signUp($email)', () {});
  @override
  Future<void> signOut() => _call('signOut', () => signedIn = false);
  @override
  Future<List<Child>> children() => _call('children', () => List.of(childList));
  @override
  Future<void> saveChild({int? id, required String nickname, required int schoolId, required int grade}) =>
      _call('saveChild(${id ?? '-'},$nickname,$schoolId,$grade)', () {
        final school = schoolList.firstWhere((s) => s.id == schoolId,
            orElse: () => School(id: schoolId, name: '학교$schoolId', sido: '경기'));
        final child = Child(id: id ?? childList.length + 1, nickname: nickname, grade: grade, school: school);
        childList = [...childList.where((c) => c.id != child.id), child];
      });
  @override
  Future<void> deleteChild(int id) => _call('deleteChild($id)', () => childList.removeWhere((c) => c.id == id));
  @override
  Future<List<School>> searchSchools(String query) =>
      _call('searchSchools($query)', () => schoolList.where((s) => s.name.contains(query)).toList());
  @override
  Future<Set<Region>> regions() => _call('regions', () => Set.of(regionSet));
  @override
  Future<void> saveRegions(Set<Region> regions) => _call('saveRegions', () => regionSet = Set.of(regions));
  @override
  Future<List<ProgramItem>> programs({int? grade, DateTime? from, DateTime? to}) =>
      _call('programs($grade,$from,$to)', () => List.of(programList));
  @override
  Future<Set<int>> favoriteIds() => _call('favoriteIds', () => Set.of(favorites));
  @override
  Future<void> setFavorite(int programId, bool on) => _call('setFavorite($programId,$on)', () {
        on ? favorites.add(programId) : favorites.remove(programId);
      });
}
