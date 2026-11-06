import 'package:eduapp/data/models.dart';
import 'package:eduapp/screens/program_detail_screen.dart';
import 'package:eduapp/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_repository.dart';

final program = ProgramItem(
  id: 3,
  title: '공간 오감',
  institutionName: '국립중앙박물관',
  url: 'https://www.museum.go.kr/x',
  startsOn: DateTime(2026, 11, 3),
  endsOn: DateTime(2026, 11, 28),
  applyEndsAt: DateTime(2026, 11, 26, 23, 59),
  description: '전시 학습. ' * 60,
);

Future<List<Uri>> open(WidgetTester t, {bool openResult = true, double scale = 1}) async {
  final opened = <Uri>[];
  await t.pumpWidget(MaterialApp(
    theme: buildTheme(Brightness.light),
    builder: (ctx, child) =>
        MediaQuery(data: MediaQuery.of(ctx).copyWith(textScaler: TextScaler.linear(scale)), child: child!),
    home: ProgramDetailScreen(
      repo: FakeRepository(signedIn: true),
      program: program,
      favorite: false,
      now: () => DateTime(2026, 11, 6, 20),
      open: (u) async {
        opened.add(u);
        return openResult;
      },
    ),
  ));
  await t.pumpAndSettle();
  return opened;
}

void main() {
  testWidgets('shows fields', (t) async {
    await open(t);
    expect(find.text('국립중앙박물관'), findsOneWidget);
    expect(find.text('11/3(화)~11/28(토)'), findsOneWidget);
    expect(find.text('초등 전체'), findsOneWidget);
    expect(find.text('신청 마감 11/26(목) 23:59'), findsOneWidget);
    expect(find.textContaining('시작'), findsNothing);
    expect(find.text('기관 페이지에서 확인해요'), findsOneWidget);
  });

  testWidgets('apply button opens institution page', (t) async {
    final opened = await open(t);
    await t.tap(find.text('기관 페이지에서 신청'));
    await t.pumpAndSettle();
    expect(opened, [Uri.parse('https://www.museum.go.kr/x')]);
  });

  testWidgets('open failure', (t) async {
    await open(t, openResult: false);
    await t.tap(find.text('기관 페이지에서 신청'));
    await t.pumpAndSettle();
    expect(find.text('기관 페이지를 열지 못했어요'), findsOneWidget);
  });

  testWidgets('no overflow at textScale 2.0', (t) async {
    await open(t, scale: 2.0);
    expect(t.takeException(), isNull);
  });
}
