import 'package:eduapp/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('style guide colors', () {
    final light = buildTheme(Brightness.light);
    final dark = buildTheme(Brightness.dark);
    expect(light.colorScheme.primary, const Color(0xFF2F6B4F));
    expect(dark.colorScheme.primary, const Color(0xFF7FC4A0));
    expect(light.extension<EduColors>()!.warning, const Color(0xFFB7791F));
    expect(light.colorScheme.error, const Color(0xFFB3412F));
  });
}
