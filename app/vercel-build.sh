#!/usr/bin/env bash
# Vercel 빌드: Flutter를 받아 웹으로 빌드한다. 환경변수 SUPABASE_URL, SUPABASE_ANON_KEY 필요(Vercel 프로젝트 설정).
set -euo pipefail
: "${SUPABASE_URL:?}" "${SUPABASE_ANON_KEY:?}"
FLUTTER_VERSION=3.47.9
# shortcut: 매 배포마다 Flutter를 새로 받는다(캐시 없음, 빌드 수 분 추가), 느려지면 캐시 도입
FLUTTER_DIR="${FLUTTER_DIR:-$HOME/flutter}"
[ -x "$FLUTTER_DIR/bin/flutter" ] || git clone --depth 1 -b "$FLUTTER_VERSION" https://github.com/flutter/flutter "$FLUTTER_DIR"
export PATH="$FLUTTER_DIR/bin:$PATH"
flutter config --no-analytics >/dev/null
flutter build web --release --dart-define=SUPABASE_URL="$SUPABASE_URL" --dart-define=SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY"
