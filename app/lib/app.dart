import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'data/repository.dart';
import 'screens/child_edit_screen.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'screens/region_screen.dart';
import 'theme.dart';

enum _Step { loading, login, child, regions, home, error }

/// 로그인 → (자녀 없으면) 자녀 추가 → (지역 없으면) 지역 선택 → 홈.
class EduApp extends StatefulWidget {
  const EduApp({super.key, required this.repo});
  final EduRepository repo;

  @override
  State<EduApp> createState() => _EduAppState();
}

class _EduAppState extends State<EduApp> {
  _Step _step = _Step.loading;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final repo = widget.repo;
    if (!repo.signedIn) return setState(() => _step = _Step.login);
    try {
      final step = (await repo.children()).isEmpty
          ? _Step.child
          : (await repo.regions()).isEmpty
              ? _Step.regions
              : _Step.home;
      if (mounted) setState(() => _step = step);
    } catch (_) {
      if (mounted) setState(() => _step = _Step.error);
    }
  }

  Widget _screen() => switch (_step) {
        _Step.loading => const Scaffold(body: Center(child: CircularProgressIndicator())),
        _Step.login => LoginScreen(repo: widget.repo, onSignedIn: _refresh),
        _Step.child => ChildEditScreen(repo: widget.repo, onDone: _refresh),
        _Step.regions => RegionScreen(repo: widget.repo, onDone: _refresh),
        _Step.home => HomeShell(repo: widget.repo, onSignedOut: _refresh),
        _Step.error => Scaffold(
            body: Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Text('정보를 불러오지 못했어요'),
                const SizedBox(height: 16),
                OutlinedButton(onPressed: _refresh, child: const Text('다시 시도')),
              ]),
            ),
          ),
      };

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'eduApp',
        theme: buildTheme(Brightness.light),
        darkTheme: buildTheme(Brightness.dark),
        locale: const Locale('ko'),
        supportedLocales: const [Locale('ko')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: KeyedSubtree(key: ValueKey(_step), child: _screen()),
      );
}
