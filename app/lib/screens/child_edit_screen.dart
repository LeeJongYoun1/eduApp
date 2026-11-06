import 'dart:async';

import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/repository.dart';

/// 자녀 추가·수정. 저장·삭제하면 pop(true).
class ChildEditScreen extends StatefulWidget {
  const ChildEditScreen({super.key, required this.repo, this.child});
  final EduRepository repo;
  final Child? child;

  @override
  State<ChildEditScreen> createState() => _ChildEditScreenState();
}

class _ChildEditScreenState extends State<ChildEditScreen> {
  late final _nickname = TextEditingController(text: widget.child?.nickname);
  late School? _school = widget.child?.school;
  late int? _grade = widget.child?.grade;
  Timer? _debounce;
  String _query = '';
  List<School>? _results; // null = 아직 검색 안 함
  String? _searchError;
  bool _busy = false;

  @override
  void dispose() {
    _debounce?.cancel();
    _nickname.dispose();
    super.dispose();
  }

  String get _name => _nickname.text.trim();
  bool get _nameOk => _name.isNotEmpty && _name.length <= 10;
  bool get _complete => _nameOk && _school != null && _grade != null;

  void _onQuery(String q) {
    _debounce?.cancel();
    setState(() {
      _query = q.trim();
      _results = null;
      _searchError = null;
    });
    if (_query.length < 2) return;
    _debounce = Timer(const Duration(milliseconds: 300), () async {
      final q = _query;
      try {
        final r = await widget.repo.searchSchools(q);
        if (mounted && q == _query) setState(() => _results = r);
      } catch (_) {
        if (mounted) setState(() => _searchError = '학교를 찾지 못했어요. 다시 시도해 주세요');
      }
    });
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
      if (mounted) Navigator.of(context).pop(true);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('저장하지 못했어요. 다시 시도해 주세요')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _delete() async {
    final c = widget.child!;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('${c.nickname} 정보를 지울까요?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('취소')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('지우기')),
        ],
      ),
    );
    if (ok == true) await _run(() => widget.repo.deleteChild(c.id));
  }

  String _schoolLabel(School s) => s.sigungu == null ? s.name : '${s.name} · ${s.sigungu}';

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).textTheme.bodySmall;
    return Scaffold(
      appBar: AppBar(title: Text(widget.child == null ? '자녀 추가' : '자녀 정보 수정')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            key: const Key('nickname'),
            controller: _nickname,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              labelText: '별명',
              helperText: '실명 대신 별명을 써 주세요',
              errorText: _name.length > 10 ? '별명은 10자까지예요' : null,
            ),
          ),
          const SizedBox(height: 24),
          Text('학교', style: Theme.of(context).textTheme.titleMedium),
          if (_school != null) Text('선택한 학교: ${_schoolLabel(_school!)}'),
          TextField(
            key: const Key('schoolQuery'),
            onChanged: _onQuery,
            decoration: const InputDecoration(hintText: '학교 이름으로 찾기 (예: 분당)'),
          ),
          if (_query.isNotEmpty && _query.length < 2)
            Padding(padding: const EdgeInsets.only(top: 8), child: Text('학교 이름을 두 글자 이상 입력해요', style: muted)),
          if (_searchError != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_searchError!)),
          if (_results != null && _results!.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text('검색 결과가 없어요. 서울·경기 초등학교만 찾을 수 있어요', style: muted),
            ),
          for (final s in _results ?? const <School>[])
            ListTile(
              title: Text(_schoolLabel(s)),
              onTap: () => setState(() {
                _school = s;
                _results = null;
              }),
            ),
          const SizedBox(height: 24),
          Text('학년', style: Theme.of(context).textTheme.titleMedium),
          Wrap(
            spacing: 8,
            children: [
              for (var g = 1; g <= 6; g++)
                ChoiceChip(label: Text('$g학년'), selected: _grade == g, onSelected: (_) => setState(() => _grade = g)),
            ],
          ),
          const SizedBox(height: 32),
          FilledButton(
            onPressed: _complete && !_busy
                ? () => _run(() => widget.repo
                    .saveChild(id: widget.child?.id, nickname: _name, schoolId: _school!.id, grade: _grade!))
                : null,
            child: const Text('저장'),
          ),
          if (widget.child != null) ...[
            const SizedBox(height: 8),
            OutlinedButton(onPressed: _busy ? null : _delete, child: const Text('삭제')),
          ],
        ],
      ),
    );
  }
}
