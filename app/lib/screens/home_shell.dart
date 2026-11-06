import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/repository.dart';
import 'child_edit_screen.dart';
import 'programs_tab.dart';
import 'region_screen.dart';

/// 하단 탭: 홈 · 체험 (우리 학교·집 실험은 계획 3·4).
class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.repo, required this.onSignedOut});
  final EduRepository repo;
  final VoidCallback onSignedOut;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_tab == 0 ? '홈' : '체험')),
      // 탭을 바꿀 때마다 새로 만든다: 홈에서 바꾼 자녀·지역이 체험 목록에 바로 반영된다.
      body: SafeArea(
        child: _tab == 0
            ? HomeTab(repo: widget.repo, onSignedOut: widget.onSignedOut)
            : ProgramsTab(repo: widget.repo),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: '홈'),
          NavigationDestination(icon: Icon(Icons.explore_outlined), selectedIcon: Icon(Icons.explore), label: '체험'),
        ],
      ),
    );
  }
}

class HomeTab extends StatefulWidget {
  const HomeTab({super.key, required this.repo, required this.onSignedOut});
  final EduRepository repo;
  final VoidCallback onSignedOut;

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> {
  List<Child>? _children;
  Set<Region>? _regions;
  bool _error = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final kids = await widget.repo.children();
      final regions = await widget.repo.regions();
      if (mounted) {
        setState(() {
          _children = kids;
          _regions = regions;
          _error = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _error = true);
    }
  }

  Future<void> _push(Widget screen) async {
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => screen));
    if (changed == true) _load();
  }

  Future<void> _signOut() async {
    try {
      await widget.repo.signOut();
    } finally {
      widget.onSignedOut();
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    if (_error) {
      return ListView(padding: const EdgeInsets.all(32), children: [
        const Text('정보를 불러오지 못했어요', textAlign: TextAlign.center),
        const SizedBox(height: 16),
        Center(child: OutlinedButton(onPressed: _load, child: const Text('다시 시도'))),
      ]);
    }
    if (_children == null) return const Center(child: CircularProgressIndicator());
    final regions = _regions!.map((r) => r.toString()).toList()..sort();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('우리 아이', style: t.titleMedium),
        for (final c in _children!)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(c.nickname),
            subtitle: Text('${c.school.name} · ${c.grade}학년'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _push(ChildEditScreen(repo: widget.repo, child: c)),
          ),
        Align(
          alignment: Alignment.centerLeft,
          child: OutlinedButton(onPressed: () => _push(ChildEditScreen(repo: widget.repo)), child: const Text('자녀 추가')),
        ),
        const SizedBox(height: 24),
        Text('관심 지역', style: t.titleMedium),
        Text(regions.join(', ')),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: OutlinedButton(onPressed: () => _push(RegionScreen(repo: widget.repo)), child: const Text('지역 바꾸기')),
        ),
        const SizedBox(height: 32),
        Align(alignment: Alignment.centerLeft, child: TextButton(onPressed: _signOut, child: const Text('로그아웃'))),
      ],
    );
  }
}
