import 'package:eduapp/data/models.dart';
import 'package:eduapp/screens/child_edit_screen.dart';
import 'package:eduapp/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_repository.dart';

const bundang = School(id: 9, name: '분당초등학교', sido: '경기', sigungu: '성남시');

Future<void> open(WidgetTester t, FakeRepository repo, {Child? child}) async {
  await t.pumpWidget(MaterialApp(theme: buildTheme(Brightness.light), home: ChildEditScreen(repo: repo, child: child)));
  await t.pumpAndSettle();
}

Future<void> search(WidgetTester t, String q) async {
  await t.enterText(find.byKey(const Key('schoolQuery')), q);
  await t.pump(const Duration(milliseconds: 350));
  await t.pumpAndSettle();
}

FilledButton saveButton(WidgetTester t) => t.widget<FilledButton>(find.widgetWithText(FilledButton, '저장'));

void main() {
  testWidgets('school search ignores short query and shows empty state', (t) async {
    final repo = FakeRepository(signedIn: true, schools: [bundang]);
    await open(t, repo);
    await search(t, '분');
    expect(repo.calls.where((c) => c.startsWith('searchSchools')), isEmpty);
    expect(find.text('학교 이름을 두 글자 이상 입력해요'), findsOneWidget);
    await search(t, '  ');
    expect(repo.calls.where((c) => c.startsWith('searchSchools')), isEmpty);
    await search(t, '없는학교');
    expect(repo.calls, contains('searchSchools(없는학교)'));
    expect(find.text('검색 결과가 없어요. 서울·경기 초등학교만 찾을 수 있어요'), findsOneWidget);
  });

  testWidgets('save enabled only when complete', (t) async {
    final repo = FakeRepository(signedIn: true, schools: [bundang]);
    await open(t, repo);
    expect(find.text('실명 대신 별명을 써 주세요'), findsOneWidget);
    await t.enterText(find.byKey(const Key('nickname')), '서준');
    await t.pump();
    expect(saveButton(t).onPressed, isNull);
    await t.enterText(find.byKey(const Key('nickname')), '가나다라마바사아자차카');
    await t.pump();
    expect(find.text('별명은 10자까지예요'), findsOneWidget);
    await t.enterText(find.byKey(const Key('nickname')), '서준');
    await search(t, '분당');
    await t.tap(find.text('분당초등학교 · 성남시'));
    await t.pumpAndSettle();
    await t.tap(find.text('4학년'));
    await t.pump();
    expect(saveButton(t).onPressed, isNotNull);
    await t.tap(find.text('저장'));
    await t.pumpAndSettle();
    expect(repo.calls, contains('saveChild(-,서준,9,4)'));
  });

  testWidgets('edit and delete', (t) async {
    const child = Child(id: 5, nickname: '서아', grade: 1, school: bundang);
    final repo = FakeRepository(signedIn: true, children: [child], schools: [bundang]);
    await open(t, repo, child: child);
    expect(find.text('서아'), findsOneWidget);
    expect(find.textContaining('분당초등학교'), findsWidgets);
    expect(saveButton(t).onPressed, isNotNull);
    await t.tap(find.text('삭제'));
    await t.pumpAndSettle();
    expect(find.text('서아 정보를 지울까요?'), findsOneWidget);
    await t.tap(find.text('지우기'));
    await t.pumpAndSettle();
    expect(repo.calls, contains('deleteChild(5)'));
  });

  testWidgets('save error shows message', (t) async {
    const child = Child(id: 5, nickname: '서아', grade: 1, school: bundang);
    final repo = FakeRepository(signedIn: true, children: [child]);
    await open(t, repo, child: child);
    repo.failWith = Exception('net');
    await t.tap(find.text('저장'));
    await t.pumpAndSettle();
    expect(find.text('저장하지 못했어요. 다시 시도해 주세요'), findsOneWidget);
    expect(find.byType(ChildEditScreen), findsOneWidget);
  });
}
