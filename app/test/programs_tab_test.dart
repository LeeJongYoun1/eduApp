import 'package:eduapp/data/models.dart';
import 'package:eduapp/screens/program_detail_screen.dart';
import 'package:eduapp/screens/programs_tab.dart';
import 'package:eduapp/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_repository.dart';

const school = School(id: 9, name: '분당초등학교', sido: '경기', sigungu: '성남시');
const seojun = Child(id: 1, nickname: '서준', grade: 4, school: school);
final now = DateTime(2026, 11, 6, 20);

ProgramItem prog(int id, {String title = '꼬마 엔지니어', DateTime? applyEndsAt}) => ProgramItem(
      id: id,
      title: title,
      institutionName: '국립과천과학관',
      url: 'https://x/$id',
      gradeMin: 3,
      gradeMax: 6,
      startsOn: DateTime(2026, 11, 7),
      endsOn: DateTime(2026, 12, 12),
      applyEndsAt: applyEndsAt,
    );

Future<void> open(WidgetTester t, FakeRepository repo, {double scale = 1}) async {
  await t.pumpWidget(MaterialApp(
    theme: buildTheme(Brightness.light),
    builder: (ctx, child) =>
        MediaQuery(data: MediaQuery.of(ctx).copyWith(textScaler: TextScaler.linear(scale)), child: child!),
    home: Scaffold(body: ProgramsTab(repo: repo, now: () => now)),
  ));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('default filter uses first child grade', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun], programs: [prog(1)]);
    await open(t, repo);
    expect(repo.calls, contains('programs(4,null,null)'));
    expect(find.text('서준 4학년'), findsOneWidget);
  });

  testWidgets('weekend filter and all grades', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun], programs: [prog(1)]);
    await open(t, repo);
    await t.tap(find.text('이번 주말'));
    await t.pumpAndSettle();
    expect(repo.calls.last, 'programs(4,${DateTime(2026, 11, 7)},${DateTime(2026, 11, 8)})');
    await t.tap(find.text('모든 학년'));
    await t.pumpAndSettle();
    expect(repo.calls.last, 'programs(null,${DateTime(2026, 11, 7)},${DateTime(2026, 11, 8)})');
  });

  testWidgets('card shows formatted fields', (t) async {
    final repo = FakeRepository(
        signedIn: true, children: [seojun], programs: [prog(1, applyEndsAt: DateTime(2026, 11, 8, 18))]);
    await open(t, repo);
    expect(find.text('국립과천과학관'), findsOneWidget);
    expect(find.text('11/7(토)~12/12(토) · 초3~6'), findsOneWidget);
    expect(find.text('마감 임박'), findsOneWidget);
  });

  testWidgets('favorite toggle and favorites-only filter', (t) async {
    final repo = FakeRepository(
        signedIn: true, children: [seojun], programs: [prog(1, title: '하나'), prog(2, title: '둘')]);
    await open(t, repo);
    await t.tap(find.byIcon(Icons.star_border).first);
    await t.pumpAndSettle();
    expect(repo.calls, contains('setFavorite(1,true)'));
    expect(find.byIcon(Icons.star), findsOneWidget);
    await t.tap(find.text('관심만'));
    await t.pumpAndSettle();
    expect(find.text('하나'), findsOneWidget);
    expect(find.text('둘'), findsNothing);
  });

  testWidgets('favorite rollback on error', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun], programs: [prog(1)]);
    await open(t, repo);
    repo.failWith = Exception('net');
    await t.tap(find.byIcon(Icons.star_border));
    await t.pumpAndSettle();
    expect(find.byIcon(Icons.star_border), findsOneWidget);
    expect(find.text('관심 표시를 저장하지 못했어요'), findsOneWidget);
  });

  testWidgets('load error shows retry', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun], programs: [prog(1, title: '하나')]);
    repo.failWith = Exception('net');
    await open(t, repo);
    expect(find.text('프로그램을 불러오지 못했어요'), findsOneWidget);
    await t.tap(find.text('다시 시도'));
    await t.pumpAndSettle();
    expect(find.text('하나'), findsOneWidget);
  });

  testWidgets('empty state', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun]);
    await open(t, repo);
    await t.tap(find.text('모든 학년'));
    await t.pumpAndSettle();
    expect(find.text('관심 지역에 진행 중인 프로그램이 없어요'), findsOneWidget);
    expect(find.text('지역 바꾸기'), findsOneWidget);
  });

  testWidgets('no overflow at textScale 2.0', (t) async {
    final repo = FakeRepository(
        signedIn: true,
        children: [seojun],
        programs: [prog(1, title: '가' * 40, applyEndsAt: DateTime(2026, 11, 8, 18))]);
    await open(t, repo, scale: 2.0);
    expect(t.takeException(), isNull);
  });

  testWidgets('tap card opens detail', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun], programs: [prog(1, title: '하나')]);
    await open(t, repo);
    await t.tap(find.text('하나'));
    await t.pumpAndSettle();
    expect(find.byType(ProgramDetailScreen), findsOneWidget);
  });

  testWidgets('empty because of grade offers all grades', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun]);
    await open(t, repo);
    expect(find.text('4학년에 맞는 프로그램이 없어요'), findsOneWidget);
    repo.programList = [prog(1, title: '하나')];
    await t.tap(find.text('모든 학년 보기'));
    await t.pumpAndSettle();
    expect(repo.calls.last, 'programs(null,null,null)');
    expect(find.text('하나'), findsOneWidget);
  });
}
