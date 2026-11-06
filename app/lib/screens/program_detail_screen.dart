import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/models.dart';
import '../data/repository.dart';
import '../format.dart';
import '../theme.dart';

/// 체험 상세. 닫을 때 현재 관심 상태(bool)를 돌려준다.
class ProgramDetailScreen extends StatefulWidget {
  ProgramDetailScreen({
    super.key,
    required this.repo,
    required this.program,
    required this.favorite,
    DateTime Function()? now,
    Future<bool> Function(Uri)? open,
  })  : now = now ?? (() => kst(DateTime.now())),
        open = open ?? ((u) => launchUrl(u, mode: LaunchMode.externalApplication));
  final EduRepository repo;
  final ProgramItem program;
  final bool favorite;
  final DateTime Function() now;
  final Future<bool> Function(Uri) open;

  @override
  State<ProgramDetailScreen> createState() => _ProgramDetailScreenState();
}

class _ProgramDetailScreenState extends State<ProgramDetailScreen> {
  late bool _favorite = widget.favorite;

  void _snack(String text) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  Future<void> _toggleFavorite() async {
    final on = !_favorite;
    setState(() => _favorite = on);
    try {
      await widget.repo.setFavorite(widget.program.id, on);
    } catch (_) {
      if (!mounted) return;
      setState(() => _favorite = !on);
      _snack('관심 표시를 저장하지 못했어요');
    }
  }

  Future<void> _apply() async {
    bool ok;
    try {
      ok = await widget.open(Uri.parse(widget.program.url));
    } catch (_) {
      ok = false;
    }
    if (!ok && mounted) _snack('기관 페이지를 열지 못했어요');
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.program;
    final now = widget.now();
    final t = Theme.of(context).textTheme;
    final c = Theme.of(context).extension<EduColors>()!;
    Widget field(String label, String value) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: t.bodySmall?.copyWith(color: c.textMuted)),
            Text(value, style: t.bodyLarge),
          ]),
        );
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.of(context).pop(_favorite);
      },
      child: Scaffold(
        appBar: AppBar(actions: [
          IconButton(
            onPressed: _toggleFavorite,
            icon: Icon(_favorite ? Icons.star : Icons.star_border,
                color: c.accent, semanticLabel: _favorite ? '관심 해제' : '관심 표시'),
          ),
        ]),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(p.title, style: t.titleLarge),
            const SizedBox(height: 16),
            field('기관', p.institutionName),
            field('기간', fmtPeriod(p.startsOn, p.endsOn, now)),
            field('대상', fmtGrades(p.gradeMin, p.gradeMax)),
            field('신청', fmtApply(p.applyStartsAt, p.applyEndsAt, now)),
            field('비용', p.fee ?? '기관 페이지에서 확인해요'),
            if (p.description != null) field('소개', p.description!),
          ],
        ),
        bottomNavigationBar: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton(onPressed: _apply, child: const Text('기관 페이지에서 신청')),
          ),
        ),
      ),
    );
  }
}
