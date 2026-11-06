import 'package:flutter/material.dart';

/// 알약 모양 꼬리표: 연한 배경 + 진한 글자 (스타일 가이드 §4).
class EduChip extends StatelessWidget {
  const EduChip(this.label, {super.key, required this.color});
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(999)),
        child: Text(label, style: Theme.of(context).textTheme.labelLarge?.copyWith(color: color)),
      );
}
