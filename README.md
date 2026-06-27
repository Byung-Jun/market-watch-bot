# 주간 시장 워치리스트 봇

TradingAgents로 워치리스트 16종목을 매주 분석해서 텔레그램으로 받는 봇.
GitHub Actions에서 일요일 밤 자동 실행된다.

## 파일 구성
- `run_watchlist.py` — 메인 러너 (종목·모델 설정은 파일 상단에서 편집)
- `.github/workflows/weekly.yml` — 자동 실행 스케줄 + 수동 실행 버튼

## 준비 (GitHub Secrets)
repo → **Settings → Secrets and variables → Actions → Repository secrets**에
아래 3개 등록:

| 이름 | 값 |
|---|---|
| `GOOGLE_API_KEY` | Gemini API 키 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 텔레그램 chat id |

## 첫 실행 (수동)
1. repo **Actions** 탭
2. 왼쪽에서 **Weekly Market Watch** 선택
3. 오른쪽 **Run workflow** 버튼 → 실행
4. 로그를 보며 진행 확인. 끝나면 텔레그램으로 리포트 도착.

수동 실행으로 먼저 테스트한 뒤, 문제없으면 매주 자동으로 돈다.

## 종목 바꾸기
`run_watchlist.py` 상단 `WATCHLIST`만 수정. (한국 주식은 `.KS`/`.KQ` 접미사)

## 실행 주기 바꾸기
`weekly.yml`의 `cron` 수정. 예) 평일 매일 → `"0 13 * * 1-5"` (UTC 기준).

## 알아둘 점
- **무료 티어 한도**: Gemini 무료는 분당 약 10회 제한이라, 종목 사이에 30초씩
  쉬며 천천히 돈다. 16종목 한 번에 30~50분 걸릴 수 있음(정상).
- **레이트리밋(429)이 잦으면**: Google Cloud에서 결제(billing)를 켜면 분당 한도가
  크게 풀린다. Flash는 호출당 단가가 매우 낮아 주 1회 16종목이면 월 비용은 거의 없음.
- **데이터 부족 시**: 기본은 Yahoo Finance(무료). 데이터 에러가 나면 Alpha Vantage
  무료 키를 `ALPHA_VANTAGE_API_KEY` 시크릿으로 추가하고 `weekly.yml`의 주석 해제.
- **AQ. Gemini 키**: 정상이다(새 표준). 워크플로가 최신 구글 SDK를 깔아 호환을 맞춘다.
  혹시 401이 뜨면 키가 아니라 SDK 버전 문제.
- **스케줄 지연**: GitHub Actions 예약 실행은 부하에 따라 수십 분 늦을 수 있고,
  repo가 60일간 비활성이면 자동 실행이 멈춘다(아무 커밋이나 하면 재개).

## 주의
연구·참고용 분석이며 투자 조언이 아니다. 매수/매도 신호를 곧이곧대로 따르지 말 것.
특히 신규 상장주(SPCX)·UAM 종목은 데이터가 얇아 분석이 부분적이다.
