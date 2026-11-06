# eduApp 앱 (Flutter, Android)

## 준비
- Flutter stable, Android SDK 36 (`flutter doctor`로 확인)
- `app/env.json` (커밋하지 않음):
  ```json
  {"SUPABASE_URL": "https://<project>.supabase.co", "SUPABASE_ANON_KEY": "<publishable 또는 anon 키>"}
  ```
  앱에는 공개용 키만 넣는다. service_role/secret 키는 절대 넣지 않는다.

## 명령
```bash
cd app
flutter test                 # 화면·형식 테스트 (가짜 repository 사용)
flutter analyze
flutter run --dart-define-from-file=env.json
flutter build apk --release --dart-define-from-file=env.json   # build/app/outputs/flutter-apk/app-release.apk
```

## 구조
- `lib/data/repository.dart` — 데이터 접근 인터페이스 (모든 Supabase 호출은 `supabase_repository.dart` 한 곳)
- `lib/screens/` — 로그인, 홈, 자녀, 지역, 체험 목록·상세
- `lib/format.dart` — 날짜·학년·신청 기간 표시 (KST 고정)
- `lib/theme.dart` — 스타일 가이드 색·글자
