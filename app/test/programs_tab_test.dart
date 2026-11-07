import 'dart:async';

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

  group('school holiday filter', () {
    ProgramItem on(int id, String title, DateTime? start, DateTime? end) => ProgramItem(
        id: id, title: title, institutionName: '기관', url: 'https://x/$id', gradeMin: 3, gradeMax: 6, startsOn: start, endsOn: end);
    final nov21 = DateTime(2026, 11, 21);

    Future<void> chipOn(WidgetTester t) async {
      await t.tap(find.text('우리 학교 쉬는 날'));
      await t.pumpAndSettle();
    }

    testWidgets('holiday filter keeps only programs on holidays', (t) async {
      final repo = FakeRepository(signedIn: true, children: [seojun], programs: [
        on(1, '쉬는날체험', nov21, nov21),
        on(2, '평일체험', DateTime(2026, 11, 24), DateTime(2026, 11, 24)),
        on(3, '날짜없음', null, null),
      ])
        ..holidaySet = {nov21};
      await open(t, repo);
      expect(find.text('평일체험'), findsOneWidget);
      await chipOn(t);
      expect(repo.calls, contains('holidays(9,${DateTime(2026, 11, 6)},${DateTime(2027, 11, 6)})'));
      expect(find.text('쉬는날체험'), findsOneWidget);
      expect(find.text('평일체험'), findsNothing);
      expect(find.text('날짜없음'), findsNothing);
      await chipOn(t);
      expect(find.text('평일체험'), findsOneWidget);
    });

    testWidgets('multi day program overlapping holiday is kept', (t) async {
      final repo = FakeRepository(signedIn: true, children: [seojun], programs: [
        on(1, '걸침', DateTime(2026, 11, 20), DateTime(2026, 11, 23)),
        on(2, '이후만', DateTime(2026, 11, 22), DateTime(2026, 11, 23)),
        on(3, '시작일만', nov21, null),
        on(4, '시작일만아님', DateTime(2026, 11, 22), null),
        on(5, '종료일만', null, nov21),
      ])
        ..holidaySet = {nov21};
      await open(t, repo);
      await chipOn(t);
      expect(find.text('걸침'), findsOneWidget);
      expect(find.text('이후만'), findsNothing);
      expect(find.text('시작일만'), findsOneWidget);
      expect(find.text('시작일만아님'), findsNothing);
      expect(find.text('종료일만'), findsOneWidget);
    });

    testWidgets('no holidays shows notice', (t) async {
      final repo = FakeRepository(signedIn: true, children: [seojun], programs: [on(1, '하나', nov21, nov21)]);
      await open(t, repo);
      await chipOn(t);
      expect(find.text('쉬는 날 정보가 아직 없어요'), findsOneWidget);
      expect(find.text('하나'), findsNothing);
    });

    testWidgets('holiday load error does not break list', (t) async {
      final repo = FakeRepository(signedIn: true, children: [seojun], programs: [on(1, '하나', nov21, nov21)])
        ..holidaySet = {nov21};
      await open(t, repo);
      repo.failWith = Exception('net');
      // failWith는 다음 호출 한 번에 던져지므로 programs/children 이후인 이 시점에 holidays가 받는다
      await chipOn(t);
      expect(find.text('쉬는 날 정보를 불러오지 못했어요'), findsOneWidget);
      expect(find.text('하나'), findsOneWidget);
      expect(t.widget<FilterChip>(find.widgetWithText(FilterChip, '우리 학교 쉬는 날')).selected, isFalse);
    });

    testWidgets('chip hidden without child', (t) async {
      await open(t, FakeRepository(signedIn: true));
      expect(find.text('우리 학교 쉬는 날'), findsNothing);
      expect(find.text('관심만'), findsOneWidget);
    });

    testWidgets('changing child refetches and ignores stale holiday response', (t) async {
      const hajun = Child(id: 2, nickname: '하준', grade: 2, school: School(id: 10, name: '정자초', sido: '경기'));
      final nov25 = DateTime(2026, 11, 25);
      final repo = FakeRepository(signedIn: true, children: [seojun, hajun], programs: [
        on(1, '이십일일', nov21, nov21),
        on(2, '이십오일', nov25, nov25),
      ])
        ..holidaySet = {nov21}
        ..holdHolidays[9] = Completer<void>();
      await open(t, repo);
      await t.tap(find.text('우리 학교 쉬는 날'));
      await t.pump();
      repo.holidaySet = {nov25};
      await t.tap(find.text('하준 2학년'));
      await t.pumpAndSettle();
      expect(repo.calls.where((c) => c.startsWith('holidays(10,')), hasLength(1));
      expect(find.text('이십오일'), findsOneWidget);
      repo.holdHolidays[9]!.complete(); // 늦게 도착한 첫 자녀의 응답
      await t.pumpAndSettle();
      expect(find.text('이십오일'), findsOneWidget);
      expect(find.text('이십일일'), findsNothing);
    });

    testWidgets('no overflow at textScale 2.0 with holiday chip', (t) async {
      final repo = FakeRepository(signedIn: true, children: [seojun], programs: [prog(1)]);
      await open(t, repo, scale: 2.0);
      expect(find.text('우리 학교 쉬는 날', skipOffstage: false), findsOneWidget);
      expect(t.takeException(), isNull);
    });
  });
}
