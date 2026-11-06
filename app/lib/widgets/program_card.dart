import 'package:flutter/material.dart';

import '../data/models.dart';
import '../format.dart';
import '../theme.dart';
import 'edu_chip.dart';

class ProgramCard extends StatelessWidget {
  const ProgramCard({
    super.key,
    required this.program,
    required this.favorite,
    required this.onFavorite,
    required this.now,
    this.onTap,
  });
  final ProgramItem program;
  final bool favorite;
  final VoidCallback onFavorite;
  final DateTime now;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final c = Theme.of(context).extension<EduColors>()!;
    final p = program;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 4, 16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(p.institutionName, style: t.bodySmall?.copyWith(color: c.textMuted)),
                    Text(p.title, style: t.titleMedium),
                    const SizedBox(height: 4),
                    Text('${fmtPeriod(p.startsOn, p.endsOn, now)} · ${fmtGrades(p.gradeMin, p.gradeMax)}',
                        style: t.labelLarge),
                    if (closingSoon(p.applyEndsAt, now)) ...[
                      const SizedBox(height: 8),
                      EduChip('마감 임박', color: c.danger),
                    ],
                  ],
                ),
              ),
              IconButton(
                onPressed: onFavorite,
                icon: Icon(favorite ? Icons.star : Icons.star_border,
                    color: c.accent, semanticLabel: favorite ? '관심 해제' : '관심 표시'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
