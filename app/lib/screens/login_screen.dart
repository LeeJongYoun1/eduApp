import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart' show AuthException;

import '../data/repository.dart';

final _emailRe = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.repo, required this.onSignedIn});
  final EduRepository repo;
  final VoidCallback onSignedIn;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  String? _emailError, _passwordError, _message;
  bool _busy = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  bool _validate() {
    setState(() {
      _emailError = _emailRe.hasMatch(_email.text.trim()) ? null : '이메일 주소를 확인해요';
      _passwordError = _password.text.length >= 6 ? null : '비밀번호는 6자 이상이에요';
      _message = null;
    });
    return _emailError == null && _passwordError == null;
  }

  Future<void> _submit({required bool signUp}) async {
    if (!_validate()) return;
    setState(() => _busy = true);
    final email = _email.text.trim();
    try {
      if (signUp) {
        await widget.repo.signUp(email, _password.text);
        setState(() => _message = '가입 확인 메일을 보냈어요. 메일의 링크를 누른 뒤 로그인해요.');
      } else {
        await widget.repo.signIn(email, _password.text);
        widget.onSignedIn();
      }
    } catch (e) {
      final unconfirmed = !signUp && e is AuthException && e.code == 'email_not_confirmed';
      setState(
        () => _message = unconfirmed
            ? '가입 확인 메일의 링크를 먼저 눌러요.'
            : signUp
            ? '가입하지 못했어요. 이미 가입한 이메일인지 확인해요.'
            : '로그인하지 못했어요. 이메일과 비밀번호를 확인해요.',
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const SizedBox(height: 32),
            Text('eduApp', style: Theme.of(context).textTheme.titleLarge),
            const Text('아이가 배우는 내용에 맞는 체험을 한곳에서 찾아요.'),
            const SizedBox(height: 32),
            TextField(
              key: const Key('email'),
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              decoration: InputDecoration(labelText: '이메일', errorText: _emailError),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('password'),
              controller: _password,
              obscureText: true,
              decoration: InputDecoration(labelText: '비밀번호', errorText: _passwordError),
            ),
            const SizedBox(height: 24),
            FilledButton(onPressed: _busy ? null : () => _submit(signUp: false), child: const Text('로그인')),
            const SizedBox(height: 8),
            OutlinedButton(onPressed: _busy ? null : () => _submit(signUp: true), child: const Text('처음이에요 · 가입하기')),
            if (_message != null) Padding(padding: const EdgeInsets.only(top: 16), child: Text(_message!)),
          ],
        ),
      ),
    );
  }
}
