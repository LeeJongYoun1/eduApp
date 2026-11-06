import 'package:eduapp/screens/login_screen.dart';
import 'package:eduapp/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart' show AuthException;

import 'fake_repository.dart';

Future<void> open(WidgetTester t, FakeRepository repo, {VoidCallback? onSignedIn}) async {
  await t.pumpWidget(MaterialApp(
      theme: buildTheme(Brightness.light), home: LoginScreen(repo: repo, onSignedIn: onSignedIn ?? () {})));
  await t.pumpAndSettle();
}

Future<void> fill(WidgetTester t, String email, String pw) async {
  await t.enterText(find.byKey(const Key('email')), email);
  await t.enterText(find.byKey(const Key('password')), pw);
}

void main() {
  testWidgets('validates input before calling repo', (t) async {
    final repo = FakeRepository();
    await open(t, repo);
    await fill(t, 'not-an-email', '123');
    await t.tap(find.text('로그인'));
    await t.pumpAndSettle();
    expect(find.text('이메일 주소를 확인해요'), findsOneWidget);
    expect(find.text('비밀번호는 6자 이상이에요'), findsOneWidget);
    expect(repo.calls, isEmpty);
  });

  testWidgets('signs in', (t) async {
    final repo = FakeRepository();
    var signedIn = false;
    await open(t, repo, onSignedIn: () => signedIn = true);
    await fill(t, 'a@b.kr', '123456');
    await t.tap(find.text('로그인'));
    await t.pumpAndSettle();
    expect(repo.calls, ['signIn(a@b.kr)']);
    expect(signedIn, isTrue);
  });

  testWidgets('sign in error', (t) async {
    final repo = FakeRepository()..failWith = Exception('bad');
    await open(t, repo);
    await fill(t, 'a@b.kr', '123456');
    await t.tap(find.text('로그인'));
    await t.pumpAndSettle();
    expect(find.text('로그인하지 못했어요. 이메일과 비밀번호를 확인해요.'), findsOneWidget);
  });

  testWidgets('sign up shows confirmation message', (t) async {
    final repo = FakeRepository();
    await open(t, repo);
    await fill(t, 'a@b.kr', '123456');
    await t.tap(find.text('처음이에요 · 가입하기'));
    await t.pumpAndSettle();
    expect(repo.calls, ['signUp(a@b.kr)']);
    expect(find.text('가입 확인 메일을 보냈어요. 메일의 링크를 누른 뒤 로그인해요.'), findsOneWidget);
  });

  testWidgets('unconfirmed email gets its own message', (t) async {
    final repo = FakeRepository()..failWith = const AuthException('Email not confirmed', code: 'email_not_confirmed');
    await open(t, repo);
    await fill(t, 'a@b.kr', '123456');
    await t.tap(find.text('로그인'));
    await t.pumpAndSettle();
    expect(find.text('가입 확인 메일의 링크를 먼저 눌러요.'), findsOneWidget);
  });

  testWidgets('sign up with auto-confirm goes straight in', (t) async {
    final repo = FakeRepository(autoConfirm: true);
    var signedIn = false;
    await open(t, repo, onSignedIn: () => signedIn = true);
    await fill(t, 'a@b.kr', '123456');
    await t.tap(find.text('처음이에요 · 가입하기'));
    await t.pumpAndSettle();
    expect(signedIn, isTrue);
    expect(find.textContaining('확인 메일을 보냈어요'), findsNothing);
  });
}
