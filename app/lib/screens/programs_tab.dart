import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/repository.dart';
import '../format.dart';
import '../widgets/program_card.dart';
import 'program_detail_screen.dart';
import 'region_screen.dart';

enum _Dates { all, weekend, custom }

/// 체험 탭: 관심 지역의 진행 중/예정 프로그램 + 학년·날짜·관심 필터.
class ProgramsTab extends StatefulWidget {
  ProgramsTab({super.key, required this.repo, DateTime Function()? now}) : now = now ?? (() => kst(DateTime.now()));
  final EduRepository repo;
  final DateTime Function() now;

  @override
  State<ProgramsTab> createState() => _ProgramsTabState();
}

class _ProgramsTabState extends State<ProgramsTab> {
  List<Child>? _children;
  Child? _child; // null = 모든 학년
  _Dates _dates = _Dates.all;
  (DateTime, DateTime)? _range;
  bool _favOnly = false;
  Set<int> _favorites = {};
  List<ProgramItem>? _programs;
  bool _loading = true;
  bool _error = false;
  bool _holidayOn = false;
  Set<DateTime>? _holidays; // null = 불러오는 중
  int _holidayId = 0; // 늦게 도착한 이전 자녀의 쉬는 날이 덮어쓰지 않게 한다

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = false;
    });
    try {
      if (_children == null) {
        final kids = await widget.repo.children();
        _children = kids;
        _child = kids.isEmpty ? null : kids.first;
      }
      final favorites = await widget.repo.favoriteIds();
      final programs = await widget.repo.programs(grade: _child?.grade, from: _range?.$1, to: _range?.$2);
      if (!mounted) return;
      setState(() {
        _favorites = favorites;
        _programs = programs;
        _loading = false;
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = true;
          _loading = false;
        });
      }
    }
  }

  void _pickChild(Child? c) {
    _child = c;
    if (_holidayOn) _loadHolidays();
    _load();
  }

  // 학년 필터가 "모든 학년"이면 첫 자녀의 학교를 따른다.
  Child? get _holidayChild => _child ?? (_children?.isEmpty ?? true ? null : _children!.first);

  Future<void> _loadHolidays() async {
    final id = ++_holidayId;
    final child = _holidayChild;
    if (child == null) return;
    setState(() {
      _holidayOn = true;
      _holidays = null;
    });
    final today = widget.now();
    final from = DateTime(today.year, today.month, today.day);
    try {
      // shortcut: 오늘~1년 뒤만 가져온다, 더 먼 프로그램이 생기면 프로그램 날짜 범위로 바꾼다.
      final days = await widget.repo.holidays(child.school.id, from, from.add(const Duration(days: 365)));
      if (!mounted || id != _holidayId) return;
      setState(() => _holidays = days);
    } catch (_) {
      if (!mounted || id != _holidayId) return;
      setState(() => _holidayOn = false);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('쉬는 날 정보를 불러오지 못했어요')));
    }
  }

  void _toggleHoliday(bool on) {
    if (on) {
      _loadHolidays();
    } else {
      _holidayId++;
      setState(() => _holidayOn = false);
    }
  }

  bool _onHoliday(ProgramItem p) {
    final s = p.startsOn ?? p.endsOn, e = p.endsOn ?? p.startsOn;
    if (s == null || e == null) return false;
    final from = DateTime(s.year, s.month, s.day), to = DateTime(e.year, e.month, e.day);
    return _holidays!.any((h) => !h.isBefore(from) && !h.isAfter(to));
  }

  Future<void> _pickDates(_Dates d) async {
    final today = widget.now();
    if (d == _Dates.custom) {
      final day = DateTime(today.year, today.month, today.day);
      final r = await showDateRangePicker(
        context: context,
        firstDate: day,
        lastDate: day.add(const Duration(days: 365)),
      );
      if (r == null) return;
      _range = (r.start, r.end);
    } else {
      _range = d == _Dates.weekend ? thisWeekend(today) : null;
    }
    _dates = d;
    _load();
  }

  Future<void> _toggleFavorite(int id) async {
    final on = !_favorites.contains(id);
    setState(() => on ? _favorites.add(id) : _favorites.remove(id));
    try {
      await widget.repo.setFavorite(id, on);
    } catch (_) {
      if (!mounted) return;
      setState(() => on ? _favorites.remove(id) : _favorites.add(id));
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('관심 표시를 저장하지 못했어요')));
    }
  }

  Future<void> _openDetail(ProgramItem p) async {
    final fav = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) =>
            ProgramDetailScreen(repo: widget.repo, program: p, favorite: _favorites.contains(p.id), now: widget.now),
      ),
    );
    if (fav != null && mounted) setState(() => fav ? _favorites.add(p.id) : _favorites.remove(p.id));
  }

  Future<void> _changeRegions() async {
    final saved = await Navigator.of(context)
        .push<bool>(MaterialPageRoute(builder: (_) => RegionScreen(repo: widget.repo)));
    if (saved == true) _load();
  }

  Widget _filters() {
    final today = widget.now();
    Widget choice(String label, bool selected, VoidCallback onTap) => Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(label: Text(label), selected: selected, onSelected: (_) => onTap()),
    );
    Widget row(List<Widget> chips) => SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(children: chips),
    );
    return Column(
      children: [
        row([
          for (final c in _children ?? const <Child>[])
            choice('${c.nickname} ${c.grade}학년', _child == c, () => _pickChild(c)),
          choice('모든 학년', _child == null, () => _pickChild(null)),
        ]),
        row([
          choice('전체', _dates == _Dates.all, () => _pickDates(_Dates.all)),
          choice('이번 주말', _dates == _Dates.weekend, () => _pickDates(_Dates.weekend)),
          choice(
            _dates == _Dates.custom ? fmtPeriod(_range!.$1, _range!.$2, today) : '날짜 선택',
            _dates == _Dates.custom,
            () => _pickDates(_Dates.custom),
          ),
          FilterChip(label: const Text('관심만'), selected: _favOnly, onSelected: (v) => setState(() => _favOnly = v)),
          if (_holidayChild != null)
            Padding(
              padding: const EdgeInsets.only(left: 8),
              child: FilterChip(label: const Text('우리 학교 쉬는 날'), selected: _holidayOn, onSelected: _toggleHoliday),
            ),
        ]),
      ],
    );
  }

  Widget _body() {
    if (_loading || (_holidayOn && _holidays == null)) return const Center(child: CircularProgressIndicator());
    if (_error) {
      return _message('프로그램을 불러오지 못했어요', OutlinedButton(onPressed: _load, child: const Text('다시 시도')));
    }
    if (_holidayOn && _holidays!.isEmpty) return _message('쉬는 날 정보가 아직 없어요', null);
    var list = _favOnly ? _programs!.where((p) => _favorites.contains(p.id)).toList() : _programs!;
    if (_holidayOn) list = list.where(_onHoliday).toList();
    if (list.isEmpty) {
      if (_favOnly) return _message('관심 표시한 프로그램이 없어요', null);
      final child = _child;
      if (child != null) {
        return _message(
          '${child.grade}학년에 맞는 프로그램이 없어요',
          OutlinedButton(onPressed: () => _pickChild(null), child: const Text('모든 학년 보기')),
        );
      }
      return _message('관심 지역에 진행 중인 프로그램이 없어요', OutlinedButton(onPressed: _changeRegions, child: const Text('지역 바꾸기')));
    }
    final now = widget.now();
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: list.length,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (_, i) => ProgramCard(
        program: list[i],
        favorite: _favorites.contains(list[i].id),
        onFavorite: () => _toggleFavorite(list[i].id),
        now: now,
        onTap: () => _openDetail(list[i]),
      ),
    );
  }

  Widget _message(String text, Widget? action) => ListView(
    padding: const EdgeInsets.all(32),
    children: [
      Text(text, textAlign: TextAlign.center),
      if (action != null) ...[const SizedBox(height: 16), Center(child: action)],
    ],
  );

  @override
  Widget build(BuildContext context) => Column(
    children: [
      const SizedBox(height: 8),
      _filters(),
      Expanded(child: _body()),
    ],
  );
}
