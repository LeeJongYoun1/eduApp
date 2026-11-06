import 'package:flutter/material.dart';

/// 스타일 가이드(docs/09-style-guide.md) 색 토큰 중 ColorScheme에 없는 것.
class EduColors extends ThemeExtension<EduColors> {
  const EduColors({
    required this.info,
    required this.warning,
    required this.accent,
    required this.danger,
    required this.textMuted,
    required this.border,
    required this.card,
  });

  final Color info, warning, accent, danger, textMuted, border, card;

  static const light = EduColors(
    info: Color(0xFF3B6EA8),
    warning: Color(0xFFB7791F),
    accent: Color(0xFFE8A13A),
    danger: Color(0xFFB3412F),
    textMuted: Color(0xFF5D665F),
    border: Color(0xFFE3E0D8),
    card: Color(0xFFFFFFFF),
  );
  static const dark = EduColors(
    info: Color(0xFF8AB4E0),
    warning: Color(0xFFE0B060),
    accent: Color(0xFFF2BC6B),
    danger: Color(0xFFE8806E),
    textMuted: Color(0xFFA3ABA5),
    border: Color(0xFF2E322E),
    card: Color(0xFF1F221F),
  );

  @override
  EduColors copyWith() => this;

  @override
  EduColors lerp(EduColors? other, double t) => t < 0.5 ? this : (other ?? this);
}

ThemeData buildTheme(Brightness b) {
  final isLight = b == Brightness.light;
  final c = isLight ? EduColors.light : EduColors.dark;
  final text = isLight ? const Color(0xFF1E2420) : const Color(0xFFECEFEC);
  final surface = isLight ? const Color(0xFFFAF8F4) : const Color(0xFF161816);
  final scheme = ColorScheme.fromSeed(seedColor: const Color(0xFF2F6B4F), brightness: b).copyWith(
    primary: isLight ? const Color(0xFF2F6B4F) : const Color(0xFF7FC4A0),
    onPrimary: isLight ? const Color(0xFFFFFFFF) : const Color(0xFF0F2A1E),
    surface: surface,
    onSurface: text,
    error: c.danger,
    outline: c.border,
  );
  final border = BorderSide(color: c.border);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: surface,
    extensions: [c],
    textTheme: const TextTheme(
      titleLarge: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, height: 1.5),
      titleMedium: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, height: 1.5),
      bodyLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w400, height: 1.5),
      bodyMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w400, height: 1.5),
      labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, height: 1.5),
      bodySmall: TextStyle(fontSize: 13, fontWeight: FontWeight.w400, height: 1.5),
    ).apply(bodyColor: text, displayColor: text),
    cardTheme: CardThemeData(
      color: c.card,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: border),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(48, 48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    dividerTheme: DividerThemeData(color: c.border, thickness: 1),
  );
}
