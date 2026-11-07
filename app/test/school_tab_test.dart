import 'package:eduapp/data/models.dart';
import 'package:eduapp/screens/school_tab.dart';
import 'package:eduapp/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_repository.dart';

School school([SchoolStatus s = SchoolStatus.done]) =>
    School(id: 9, name: '분당초등학교', sido: '경기', sigungu: '성남시', status: s);
Child kid({int id = 1, String name = '서준', int grade = 4, SchoolStatus status = SchoolStatus.done}) =>
    Child(id: id, nickname: name, grade: grade, school: school(status));

SchoolTextbook tb(String subject, {String? publisher, bool confirmed = false, bool isGuess = false}) =>
    SchoolTextbook(subject: subject, publisher: publisher, confirmed: confirmed, isGuess: isGuess);

List<SchoolTextbook> four() => [
      tb('수학', publisher: '천재교육', confirmed: true),
      tb('사회', publisher: '지학사', isGuess: true),
      tb('과학', publisher: '김영사', isGuess: true),
      tb('영어'),
    ];

Future<void> open(WidgetTester t, FakeRepository repo, {double scale = 1}) async {
  await t.pumpWidget(MaterialApp(
    theme: buildTheme(Brightness.light),
    builder: (ctx, child) =>
        MediaQuery(data: MediaQuery.of(ctx).copyWith(textScaler: TextScaler.linear(scale)), child: child!),
    home: Scaffold(body: SchoolTab(repo: repo)),
  ));
  await t.pumpAndSettle();
}

Future<void> openSheet(WidgetTester t, String subject) async {
  await t.tap(find.text(subject));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('shows four subjects with confirming chip for guesses', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid()])..textbooks[1] = four();
    await open(t, repo);
    expect(repo.calls, contains('schoolTextbooks(1)'));
    for (final s in ['수학', '사회', '과학', '영어']) {
      expect(find.text(s), findsOneWidget);
    }
    expect(find.text('천재교육'), findsOneWidget);
    // 추정 두 줄은 칩, 출판사 없는 영어는 글자만 (칩 중복 없음)
    expect(find.text('확인 중'), findsNWidgets(3));
    expect(find.text('교과서 정보를 확인하고 있어요 (내일 아침까지)'), findsNothing);
  });

  testWidgets('pending school shows waiting message', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid(status: SchoolStatus.pending)])
      ..textbooks[1] = four();
    await open(t, repo);
    expect(find.text('교과서 정보를 확인하고 있어요 (내일 아침까지)'), findsOneWidget);
  });

  testWidgets('failed and notRequested also show waiting message', (t) async {
    for (final s in [SchoolStatus.failed, SchoolStatus.notRequested]) {
      final repo = FakeRepository(signedIn: true, children: [kid(status: s)])..textbooks[1] = four();
      await open(t, repo);
      expect(find.text('교과서 정보를 확인하고 있어요 (내일 아침까지)'), findsOneWidget);
    }
  });

  testWidgets('not found school shows ask-parent message', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid(status: SchoolStatus.notFound)])
      ..textbooks[1] = four();
    await open(t, repo);
    expect(find.text('학교 공지에서 찾지 못했어요. 알고 계시면 알려주세요'), findsOneWidget);
    expect(find.text('교과서 정보를 확인하고 있어요 (내일 아침까지)'), findsNothing);
  });

  testWidgets('correct publisher saves and refreshes', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid()])..textbooks[1] = four();
    await open(t, repo);
    await openSheet(t, '사회');
    await t.enterText(find.byType(TextField), ' 비상교육 ');
    await t.pump();
    await t.tap(find.text('저장'));
    await t.pumpAndSettle();
    expect(repo.calls, contains('correctPublisher(1,사회,비상교육)'));
    expect(repo.calls.last, 'schoolTextbooks(1)');
    expect(find.text('비상교육'), findsOneWidget);
    expect(find.text('지학사'), findsNothing);
    expect(find.text('확인 중'), findsNWidgets(2)); // 과학 칩 + 영어 글자
  });

  testWidgets('publisher input rejects empty and over 20 chars', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid()])..textbooks[1] = four();
    await open(t, repo);
    await openSheet(t, '사회');
    FilledButton save() => t.widget<FilledButton>(find.widgetWithText(FilledButton, '저장'));
    await t.enterText(find.byType(TextField), '   ');
    await t.pump();
    expect(save().onPressed, isNull);
    await t.enterText(find.byType(TextField), '가' * 21);
    await t.pump();
    expect(save().onPressed, isNull);
    await t.enterText(find.byType(TextField), '가' * 20);
    await t.pump();
    expect(save().onPressed, isNotNull);
  });

  testWidgets('correct failure shows snackbar and keeps old value', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid()])..textbooks[1] = four();
    await open(t, repo);
    await openSheet(t, '사회');
    await t.enterText(find.byType(TextField), '비상교육');
    await t.pump();
    repo.failWith = Exception('net');
    await t.tap(find.text('저장'));
    await t.pumpAndSettle();
    expect(find.text('저장하지 못했어요. 다시 시도해 주세요'), findsOneWidget);
    expect(find.text('지학사'), findsOneWidget);
    expect(find.text('비상교육'), findsNothing);
  });

  testWidgets('grade under 3 shows notice', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid(grade: 2)]);
    await open(t, repo);
    expect(find.text('3학년부터 출판사를 볼 수 있어요'), findsOneWidget);
    expect(repo.calls, isNot(contains('schoolTextbooks(1)')));
  });

  testWidgets('no child shows register prompt', (t) async {
    await open(t, FakeRepository(signedIn: true));
    expect(find.text('자녀를 먼저 등록해요'), findsOneWidget);
  });

  testWidgets('load error shows retry', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid()])..textbooks[1] = four();
    repo.failWith = Exception('net');
    await open(t, repo);
    expect(find.text('불러오지 못했어요'), findsOneWidget);
    await t.tap(find.text('다시 시도'));
    await t.pumpAndSettle();
    expect(find.text('천재교육'), findsOneWidget);
  });

  testWidgets('child chips switch child when there are two', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid(), kid(id: 2, name: '하은', grade: 5)])
      ..textbooks[1] = four()
      ..textbooks[2] = [tb('수학', publisher: '동아출판', confirmed: true)];
    await open(t, repo);
    await t.tap(find.text('하은'));
    await t.pumpAndSettle();
    expect(repo.calls.last, 'schoolTextbooks(2)');
    expect(find.text('동아출판'), findsOneWidget);
  });

  testWidgets('no overflow at textScale 2.0', (t) async {
    final repo = FakeRepository(signedIn: true, children: [kid(status: SchoolStatus.pending), kid(id: 2, name: '하은하은하은')])
      ..textbooks[1] = [tb('수학', publisher: '가' * 20, isGuess: true), tb('영어')];
    await open(t, repo, scale: 2.0);
    expect(t.takeException(), isNull);
    await openSheet(t, '수학');
    expect(t.takeException(), isNull);
  });
}
