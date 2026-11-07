import 'package:eduapp/app.dart';
import 'package:eduapp/data/models.dart';
import 'package:eduapp/screens/child_edit_screen.dart';
import 'package:eduapp/screens/login_screen.dart';
import 'package:eduapp/screens/region_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_repository.dart';

const school = School(id: 9, name: '분당초등학교', sido: '경기', sigungu: '성남시');
const seojun = Child(id: 1, nickname: '서준', grade: 4, school: school);

Future<void> open(WidgetTester t, FakeRepository repo) async {
  await t.pumpWidget(EduApp(repo: repo));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('signed out → login', (t) async {
    await open(t, FakeRepository());
    expect(find.byType(LoginScreen), findsOneWidget);
  });

  testWidgets('no children → child screen, then regions, then home', (t) async {
    final repo = FakeRepository(signedIn: true, schools: [school]);
    await open(t, repo);
    expect(find.byType(ChildEditScreen), findsOneWidget);

    await t.enterText(find.byKey(const Key('nickname')), '서준');
    await t.enterText(find.byKey(const Key('schoolQuery')), '분당');
    await t.pump(const Duration(milliseconds: 350));
    await t.pumpAndSettle();
    await t.tap(find.text('분당초등학교 · 성남시'));
    await t.pumpAndSettle();
    await t.tap(find.text('4학년'));
    await t.pump();
    await t.tap(find.text('저장'));
    await t.pumpAndSettle();
    expect(find.byType(RegionScreen), findsOneWidget);

    await t.tap(find.widgetWithText(FilterChip, '서울 전체'));
    await t.pumpAndSettle();
    await t.tap(find.text('저장'));
    await t.pumpAndSettle();
    expect(find.widgetWithText(NavigationDestination, '홈'), findsOneWidget);
  });

  testWidgets('child but no regions → region screen', (t) async {
    await open(t, FakeRepository(signedIn: true, children: [seojun]));
    expect(find.byType(RegionScreen), findsOneWidget);
  });

  testWidgets('ready → home with tabs', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun], regions: {const Region('경기', '성남시')});
    await open(t, repo);
    expect(find.widgetWithText(NavigationDestination, '홈'), findsOneWidget);
    expect(find.widgetWithText(NavigationDestination, '체험'), findsOneWidget);
    expect(find.widgetWithText(NavigationDestination, '우리 학교'), findsOneWidget);
    expect(find.text('서준'), findsOneWidget);
    expect(find.textContaining('경기 성남시'), findsOneWidget);
    await t.tap(find.widgetWithText(NavigationDestination, '체험'));
    await t.pumpAndSettle();
    expect(find.text('4학년에 맞는 프로그램이 없어요'), findsOneWidget);
  });

  testWidgets('sign out returns to login', (t) async {
    final repo = FakeRepository(signedIn: true, children: [seojun], regions: {const Region('경기', '성남시')});
    await open(t, repo);
    await t.tap(find.text('로그아웃'));
    await t.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);
  });
}
