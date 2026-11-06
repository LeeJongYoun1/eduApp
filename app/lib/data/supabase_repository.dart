import 'package:supabase_flutter/supabase_flutter.dart';

import 'models.dart';
import 'repository.dart';

class SupabaseRepository implements EduRepository {
  SupabaseClient get _db => Supabase.instance.client;
  String get _uid => _db.auth.currentUser!.id;

  String _day(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  @override
  bool get signedIn => _db.auth.currentSession != null;

  @override
  Future<void> signIn(String email, String password) =>
      _db.auth.signInWithPassword(email: email, password: password);

  @override
  Future<void> signUp(String email, String password) => _db.auth.signUp(email: email, password: password);

  @override
  Future<void> signOut() => _db.auth.signOut();

  @override
  Future<List<Child>> children() async {
    final rows = await _db
        .from('children')
        .select('id,nickname,grade,school:schools(id,name,sido,sigungu)')
        .order('created_at');
    return rows.map(Child.fromJson).toList();
  }

  @override
  Future<void> saveChild({int? id, required String nickname, required int schoolId, required int grade}) async {
    final row = {'nickname': nickname, 'school_id': schoolId, 'grade': grade};
    if (id == null) {
      await _db.from('children').insert({...row, 'parent_id': _uid});
    } else {
      await _db.from('children').update(row).eq('id', id);
    }
  }

  @override
  Future<void> deleteChild(int id) => _db.from('children').delete().eq('id', id);

  @override
  Future<List<School>> searchSchools(String query) async {
    final rows = await _db.from('schools').select('id,name,sido,sigungu').ilike('name', '%$query%').order('name').limit(20);
    return rows.map(School.fromJson).toList();
  }

  @override
  Future<Set<Region>> regions() async {
    final rows = await _db.from('user_regions').select('sido,sigungu');
    return {for (final r in rows) Region(r['sido'] as String, r['sigungu'] as String)};
  }

  @override
  Future<void> saveRegions(Set<Region> regions) async {
    await _db.from('user_regions').delete().eq('user_id', _uid);
    await _db.from('user_regions').insert([
      for (final r in regions) {'user_id': _uid, 'sido': r.sido, 'sigungu': r.sigungu}
    ]);
  }

  @override
  Future<List<ProgramItem>> programs({int? grade, DateTime? from, DateTime? to}) async {
    final rows = await _db.rpc('my_programs', params: {
      'p_grade': grade,
      'p_from': from == null ? null : _day(from),
      'p_to': to == null ? null : _day(to),
    }) as List;
    return rows.map((r) => ProgramItem.fromJson(r as Map<String, dynamic>)).toList();
  }

  @override
  Future<Set<int>> favoriteIds() async {
    final rows = await _db.from('favorites').select('program_id');
    return {for (final r in rows) r['program_id'] as int};
  }

  @override
  Future<void> setFavorite(int programId, bool on) => on
      ? _db.from('favorites').upsert({'user_id': _uid, 'program_id': programId})
      : _db.from('favorites').delete().eq('program_id', programId);
}
