import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/repository.dart';
import '../regions.dart';

/// 관심 지역(서울·경기 시군구 복수 선택). 저장하면 pop(true).
class RegionScreen extends StatefulWidget {
  const RegionScreen({super.key, required this.repo, this.onDone});
  final EduRepository repo;

  /// 있으면 저장 후 pop 대신 호출 (첫 실행 흐름에서 루트 화면으로 쓸 때).
  final VoidCallback? onDone;

  @override
  State<RegionScreen> createState() => _RegionScreenState();
}

class _RegionScreenState extends State<RegionScreen> {
  Set<Region>? _selected; // null = 불러오는 중
  bool _busy = false;
  bool _loadError = false; // 실패를 빈 선택으로 보이면 저장 시 기존 지역을 덮어쓴다

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loadError = false);
    try {
      final r = await widget.repo.regions();
      if (mounted) setState(() => _selected = r);
    } catch (_) {
      if (mounted) setState(() => _loadError = true);
    }
  }

  void _toggle(Region r) => setState(() {
    final s = _selected!;
    if (s.remove(r)) return;
    if (r.sigungu.isEmpty) {
      s.removeWhere((x) => x.sido == r.sido); // 시도 전체가 개별 선택을 대신한다
    } else {
      s.remove(Region(r.sido, ''));
    }
    s.add(r);
  });

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      await widget.repo.saveRegions(_selected!);
      if (!mounted) return;
      final done = widget.onDone;
      done != null ? done() : Navigator.of(context).pop(true);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('저장하지 못했어요. 다시 시도해 주세요')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _chips(String sido) {
    Widget chip(String label, Region r) =>
        FilterChip(label: Text(label), selected: _selected!.contains(r), onSelected: (_) => _toggle(r));
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [chip('$sido 전체', Region(sido, '')), for (final g in kSigungu[sido]!) chip(g, Region(sido, g))],
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selected;
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('관심 지역'),
          bottom: const TabBar(
            tabs: [
              Tab(text: '서울'),
              Tab(text: '경기'),
            ],
          ),
        ),
        body: _loadError
            ? Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('지역 정보를 불러오지 못했어요'),
                    const SizedBox(height: 16),
                    OutlinedButton(onPressed: _load, child: const Text('다시 시도')),
                  ],
                ),
              )
            : selected == null
            ? const Center(child: CircularProgressIndicator())
            : TabBarView(children: [_chips('서울'), _chips('경기')]),
        bottomNavigationBar: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton(
              onPressed: selected != null && selected.isNotEmpty && !_busy ? _save : null,
              child: const Text('저장'),
            ),
          ),
        ),
      ),
    );
  }
}
