# Market Watch Bot

**LLM을 활용한 주간 시장 분석 및 모니터링 자동화 봇**

Market Watch Bot은 [TradingAgents](https://github.com/TauricResearch/TradingAgents)와 OpenRouter 호환 LLM을 활용하여, 사용자가 설정한 관심 종목을 자동으로 분석하고 그 결과를 Telegram으로 전달하는 프로젝트입니다.

이 프로젝트는 단순한 시장 분석 도구를 넘어, **AI를 활용한 소프트웨어 개발 및 자동화된 유지보수 workflow를 실험하기 위한 개인 OSS 프로젝트**입니다.

## 동작 방식

```text
관심 종목 목록
    ↓
TradingAgents
    ↓
LLM 기반 시장 분석
    ↓
투자 신호 추출
    ↓
Markdown 리포트 생성
    ↓
Telegram 알림
```

전체 workflow는 GitHub Actions를 통해 **매주 자동으로 실행**됩니다.

## 주요 기능

* 사용자 정의 관심 종목 목록
* 주간 시장 분석 자동화
* OpenRouter LLM 모델 선택 및 fallback 지원
* Rate Limit 발생 시 자동 재시도
* 사용 가능한 모델 자동 탐색
* Markdown 분석 리포트 생성
* JSON 요약 데이터 생성
* Telegram 알림
* GitHub Actions 기반 자동 실행
* 핵심 데이터 파싱 및 리포트 생성 로직에 대한 단위 테스트

## AI 모델 처리

여러 LLM 후보를 설정하고, 실행 시 사용 가능한 모델을 자동으로 선택할 수 있습니다.

특히 무료 또는 사용량 제한이 있는 LLM API를 사용할 경우 모델의 가용성이 시간에 따라 달라질 수 있기 때문에, 특정 모델에 문제가 발생하더라도 다른 모델로 자동 전환할 수 있도록 설계했습니다.

사용할 모델 목록은 `config.json`에서 관리하며, **Python 메인 코드를 수정하지 않고도 모델을 변경할 수 있습니다.**

## 설정

관심 종목과 사용할 LLM 모델은 다음 파일에서 설정합니다.

```text
config.json
```

예시:

```json
{
  "watchlist": {
    "Technology": ["NVDA", "MSFT"],
    "ETF": ["VOO", "QQQ"]
  }
}
```

현재 저장소의 기본 설정은 프로젝트 테스트 및 예제 실행을 위해 최소한의 종목으로 구성되어 있습니다.

## 필요한 GitHub Actions Secrets

다음 Secret을 GitHub 저장소에 등록해야 합니다.

| Secret               | 용도                     |
| -------------------- | ---------------------- |
| `OPENROUTER_API_KEY` | LLM API 인증             |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot 인증        |
| `TELEGRAM_CHAT_ID`   | 결과를 전달할 Telegram 채팅 ID |

Secret은 환경 변수로 전달되며 저장소에 직접 저장되지 않습니다.

> ⚠️ API Key, Bot Token, 비밀번호 및 기타 인증 정보를 Git 저장소에 절대 커밋하지 마세요.

## 로컬에서 실행하기

저장소를 clone합니다.

```bash
git clone https://github.com/Byung-Jun/market-watch-bot.git
cd market-watch-bot

python -m venv .venv
```

가상환경을 활성화하고 필요한 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

필요한 환경 변수를 설정합니다.

```bash
export OPENROUTER_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
```

실행합니다.

```bash
python run_watchlist.py
```

## 테스트

다음 명령어로 단위 테스트를 실행할 수 있습니다.

```bash
python -m unittest discover
```

현재 다음과 같은 핵심 기능을 테스트합니다.

* 투자 신호 추출
* Rate Limit 처리
* LLM 모델 fallback
* 리포트 생성

## GitHub Actions

자동 실행 workflow는 다음 파일에 정의되어 있습니다.

```text
.github/workflows/weekly.yml
```

GitHub Actions의 주간 스케줄을 통해 자동으로 실행되며, `workflow_dispatch`를 이용해 수동 실행할 수도 있습니다.

전체 workflow는 다음과 같습니다.

1. 필요한 패키지 설치
2. 관심 종목 시장 분석 실행
3. 분석 리포트 생성
4. 생성된 리포트를 Git 저장소에 자동 커밋
5. 분석 결과를 Telegram으로 전송

## AI 기반 개발 및 유지보수

이 프로젝트는 시장 분석 자동화뿐만 아니라 **소프트웨어 개발 lifecycle 자체에 AI를 적용하는 방법을 실험**하는 프로젝트이기도 합니다.

현재 다음 영역에서 AI-assisted development를 적용하고 있습니다.

* 요구사항 분석
* 코드 생성
* 코드 리팩터링
* 디버깅
* 테스트 코드 생성
* 코드 리뷰
* 문서화
* GitHub Issue 분석
* 유지보수 자동화

장기적인 목표는 **개인 maintainer가 AI Coding Agent를 활용하여 소프트웨어의 개발뿐만 아니라 테스트, 리뷰, 이슈 관리, 문서화 및 지속적인 유지보수까지 수행할 수 있는 workflow를 구축하는 것**입니다.

## Roadmap

* [ ] 기본 관심 종목 목록 확대
* [ ] 분석 리포트 검증 기능 개선
* [ ] 데이터 품질 검증 강화
* [ ] 자동화 테스트 확대
* [ ] GitHub Issue 자동화 개선
* [ ] AI 기반 Issue 분류 및 분석
* [ ] AI 기반 Pull Request 코드 리뷰
* [ ] Release Note 및 Changelog 자동 생성
* [ ] AI 기반 OSS 유지보수 workflow 문서화

## 면책사항

이 프로젝트는 **연구 및 교육 목적으로 제작되었습니다.**

생성된 분석 리포트는 투자 조언이 아니며, 투자 의사결정의 유일한 근거로 사용해서는 안 됩니다.

금융 데이터 및 AI가 생성한 분석 결과에는 오류가 포함될 수 있습니다. 실제 투자 의사결정을 내리기 전에 반드시 관련 정보를 직접 확인하시기 바랍니다.

## License

MIT License
