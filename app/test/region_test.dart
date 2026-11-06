import 'package:eduapp/data/models.dart';
import 'package:eduapp/regions.dart';
import 'package:eduapp/screens/region_screen.dart';
import 'package:eduapp/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_repository.dart';

Future<void> open(WidgetTester t, FakeRepository repo) async {
  await t.pumpWidget(MaterialApp(theme: buildTheme(Brightness.light), home: RegionScreen(repo: repo)));
  await t.pumpAndSettle();
}

Future<void> chip(WidgetTester t, String label) async {
  final f = find.widgetWithText(FilterChip, label);
  await t.ensureVisible(f);
  await t.tap(f);
  await t.pumpAndSettle();
}

Future<void> tab(WidgetTester t, String label) async {
  await t.tap(find.widgetWithText(Tab, label));
  await t.pumpAndSettle();
}

FilledButton saveButton(WidgetTester t) => t.widget<FilledButton>(find.widgetWithText(FilledButton, '저장'));

void main() {
  test('sigungu lists', () {
    expect(kSigungu['서울']!.length, 25);
    expect(kSigungu['경기']!.length, 31);
    expect(kSigungu['경기'], containsAll(['과천시', '성남시']));
    expect(kSigungu['서울'], contains('용산구'));
  });

  testWidgets('save disabled when nothing selected', (t) async {
    final repo = FakeRepository(signedIn: true);
    await open(t, repo);
    expect(saveButton(t).onPressed, isNull);
    await chip(t, '용산구');
    expect(saveButton(t).onPressed, isNotNull);
    await chip(t, '용산구');
    expect(saveButton(t).onPressed, isNull);
  });

  testWidgets('pick multiple and save', (t) async {
    final repo = FakeRepository(signedIn: true);
    await open(t, repo);
    await chip(t, '용산구');
    await tab(t, '경기');
    await chip(t, '성남시');
    await chip(t, '과천시');
    await t.tap(find.text('저장'));
    await t.pumpAndSettle();
    expect(repo.regionSet, {const Region('경기', '성남시'), const Region('경기', '과천시'), const Region('서울', '용산구')});
  });

  testWidgets('whole sido replaces individual', (t) async {
    final repo = FakeRepository(signedIn: true);
    await open(t, repo);
    await chip(t, '용산구');
    await chip(t, '서울 전체');
    await t.tap(find.text('저장'));
    await t.pumpAndSettle();
    expect(repo.regionSet, {const Region('서울', '')});
  });

  testWidgets('opens with existing regions selected', (t) async {
    final repo = FakeRepository(signedIn: true, regions: {const Region('서울', '용산구')});
    await open(t, repo);
    final f = find.widgetWithText(FilterChip, '용산구');
    await t.ensureVisible(f);
    expect(t.widget<FilterChip>(f).selected, isTrue);
    expect(saveButton(t).onPressed, isNotNull);
  });

  testWidgets('load error shows retry and blocks save', (t) async {
    final repo = FakeRepository(signedIn: true, regions: {const Region('서울', '용산구')})..failWith = Exception('net');
    await open(t, repo);
    expect(find.text('지역 정보를 불러오지 못했어요'), findsOneWidget);
    expect(saveButton(t).onPressed, isNull);
    await t.tap(find.text('다시 시도'));
    await t.pumpAndSettle();
    final f = find.widgetWithText(FilterChip, '용산구');
    await t.ensureVisible(f);
    expect(t.widget<FilterChip>(f).selected, isTrue);
  });
}
