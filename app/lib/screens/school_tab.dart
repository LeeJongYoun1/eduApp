import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/repository.dart';
import '../theme.dart';
import '../widgets/edu_chip.dart';

/// 우리 학교 탭: 자녀 학교의 과목별 교과서 출판사. 틀리면 학부모가 고칠 수 있다.
class SchoolTab extends StatefulWidget {
  const SchoolTab({super.key, required this.repo});
  final EduRepository repo;

  @override
  State<SchoolTab> createState() => _SchoolTabState();
}

class _SchoolTabState extends State<SchoolTab> {
  List<Child>? _children;
  Child? _child;
  List<SchoolTextbook>? _books;
  bool _loading = true;
  bool _error = false;

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
      final c = _child;
      final books = c == null || c.grade < 3 ? null : await widget.repo.schoolTextbooks(c.id);
      if (!mounted) return;
      setState(() {
        _books = books;
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

  Future<void> _edit(SchoolTextbook b) async {
    final publisher = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _PublisherSheet(subject: b.subject, initial: b.publisher ?? ''),
    );
    if (publisher == null) return;
    try {
      await widget.repo.correctPublisher(_child!.id, b.subject, publisher);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('저장하지 못했어요. 다시 시도해 주세요')));
      }
      return;
    }
    if (mounted) _load();
  }

  Widget _message(String text, [Widget? action]) => ListView(
        padding: const EdgeInsets.all(32),
        children: [
          Text(text, textAlign: TextAlign.center),
          if (action != null) ...[const SizedBox(height: 16), Center(child: action)],
        ],
      );

  Widget _banner(BuildContext context, SchoolStatus s) {
    final text = switch (s) {
      SchoolStatus.done => null,
      SchoolStatus.notFound => '학교 공지에서 찾지 못했어요. 알고 계시면 알려주세요',
      _ => '교과서 정보를 확인하고 있어요 (내일 아침까지)',
    };
    if (text == null) return const SizedBox.shrink();
    return Padding(padding: const EdgeInsets.fromLTRB(16, 8, 16, 0), child: Text(text));
  }

  Widget _row(BuildContext context, SchoolTextbook b) {
    final c = Theme.of(context).extension<EduColors>()!;
    final publisher = b.publisher;
    return ListTile(
      title: Text(b.subject),
      subtitle: Text(publisher ?? '확인 중'),
      trailing: publisher != null && (b.isGuess || !b.confirmed) ? EduChip('확인 중', color: c.warning) : null,
      onTap: () => _edit(b),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error) return _message('불러오지 못했어요', OutlinedButton(onPressed: _load, child: const Text('다시 시도')));
    final child = _child;
    if (child == null) return _message('자녀를 먼저 등록해요');
    if (_books == null) return _message('3학년부터 출판사를 볼 수 있어요');
    return ListView(children: [
      _banner(context, child.school.status),
      for (final b in _books!) _row(context, b),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final kids = _children ?? const <Child>[];
    return Column(children: [
      if (kids.length > 1)
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
          child: Row(children: [
            for (final c in kids)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(c.nickname),
                  selected: _child == c,
                  onSelected: (_) {
                    _child = c;
                    _load();
                  },
                ),
              ),
          ]),
        ),
      Expanded(child: _body(context)),
    ]);
  }
}

class _PublisherSheet extends StatefulWidget {
  const _PublisherSheet({required this.subject, required this.initial});
  final String subject;
  final String initial;

  @override
  State<_PublisherSheet> createState() => _PublisherSheetState();
}

class _PublisherSheetState extends State<_PublisherSheet> {
  late final _ctrl = TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = _ctrl.text.trim();
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${widget.subject} 출판사', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          TextField(
            controller: _ctrl,
            autofocus: true,
            decoration: const InputDecoration(hintText: '예: 비상교육', helperText: '1~20자'),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: text.isEmpty || text.length > 20 ? null : () => Navigator.of(context).pop(text),
            child: const Text('저장'),
          ),
        ]),
      ),
    );
  }
}
