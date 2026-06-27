#!/usr/bin/env python3
"""주간 시장 워치리스트 러너 — OpenRouter 버전 (SPCX 1종목 테스트).

무료 OpenRouter 모델(:free)로 TradingAgents를 돌린다.
무료 한도(하루 50요청)를 고려해 종목 1개 + 토론 0라운드로 호출 최소화.
키는 GitHub Secrets에서 OPENROUTER_API_KEY로 주입받는다.
"""

import os
import sys
import time
from datetime import date, timedelta

import requests

# ════════════════════════════════════════════════════════════════
#  여기만 편집하면 됨 (EDIT HERE)
# ════════════════════════════════════════════════════════════════

# 테스트: SPCX 1종목만.
WATCHLIST = {
    "테스트": ["SPCX"],
}

# OpenRouter 무료 모델 (도구 호출 지원 모델로 선택).
# 만약 이 모델이 안 되면 openrouter.ai/models 에서
# Price=Free + supported_parameters=tools 로 필터해서 다른 :free 모델로 교체.
DEEP_THINK_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
QUICK_THINK_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

# 호출 최소화: 토론 0라운드
MAX_DEBATE_ROUNDS = 0

# 종목 사이 대기(초). OpenRouter 무료 분당 20요청 → 여유롭게.
SLEEP_BETWEEN_TICKERS = 5

# ════════════════════════════════════════════════════════════════
#  아래부터는 건드릴 필요 없음
# ════════════════════════════════════════════════════════════════

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# TradingAgents가 OpenAI 호환 경로로 키를 읽는 경우를 대비해 같은 값 복사
if OPENROUTER_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENROUTER_API_KEY


def check_env():
    missing = [n for n, v in {
        "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }.items() if not v]
    if missing:
        print(f"[FATAL] 누락된 시크릿: {', '.join(missing)}")
        sys.exit(1)


def latest_trading_date():
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def extract_signal(text):
    t = (text or "").upper()
    if "STRONG SELL" in t:
        return "🔴", "STRONG SELL"
    if "STRONG BUY" in t:
        return "🟢", "STRONG BUY"
    for kw, emoji in [("SELL", "🔴"), ("BUY", "🟢"),
                      ("HOLD", "🟡"), ("NEUTRAL", "🟡")]:
        if kw in t:
            return emoji, kw
    return "⚪", "판단불가"


def analyze_ticker(ta, ticker, analysis_date, retries=2):
    last_err = None
    for attempt in range(1, retries + 2):
        try:
            state, decision = ta.propagate(ticker, analysis_date)
            decision_text = decision if isinstance(decision, str) else str(decision)
            final = ""
            if isinstance(state, dict):
                final = state.get("final_trade_decision") or ""
            full_text = final or decision_text
            emoji, signal = extract_signal(full_text)
            return full_text, signal, emoji
        except Exception as e:                       # noqa: BLE001
            last_err = e
            print(f"[WARN] {ticker} 시도 {attempt} 실패: {e}")
            time.sleep(20 * attempt)
    raise last_err


def send_message(text):
    for i in range(0, len(text), 4000):
        chunk = text[i:i + 4000]
        try:
            r = requests.post(
                f"{TELEGRAM_API}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": chunk},
                timeout=30,
            )
            if not r.ok:
                print(f"[WARN] 텔레그램 메시지 실패: {r.status_code} {r.text}")
        except Exception as e:                       # noqa: BLE001
            print(f"[WARN] 텔레그램 메시지 예외: {e}")


def send_document(path, caption=""):
    try:
        with open(path, "rb") as f:
            r = requests.post(
                f"{TELEGRAM_API}/sendDocument",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1000]},
                files={"document": (os.path.basename(path), f, "text/markdown; charset=utf-8")},
                timeout=120,
            )
        if not r.ok:
            print(f"[WARN] 텔레그램 파일 실패: {r.status_code} {r.text}")
    except Exception as e:                           # noqa: BLE001
        print(f"[WARN] 텔레그램 파일 예외: {e}")


def main():
    check_env()
    analysis_date = latest_trading_date()
    print(f"분석 기준일: {analysis_date}")

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
    except Exception as e:                           # noqa: BLE001
        print(f"[FATAL] TradingAgents import 실패: {e}")
        send_message(f"⚠️ 워치리스트 봇: TradingAgents 임포트 실패\n{e}")
        sys.exit(1)

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openrouter"
    config["backend_url"] = "https://openrouter.ai/api/v1"
    config["deep_think_llm"] = DEEP_THINK_MODEL
    config["quick_think_llm"] = QUICK_THINK_MODEL
    config["max_debate_rounds"] = MAX_DEBATE_ROUNDS
    config["online_tools"] = True

    ta = TradingAgentsGraph(debug=False, config=config)

    summary = [f"📊 주간 시장 리포트 ({analysis_date} 기준)", ""]
    report = [f"# 주간 시장 리포트 ({analysis_date} 기준)\n"]
    ok = fail = 0

    for theme, tickers in WATCHLIST.items():
        summary.append(f"[{theme}]")
        report.append(f"\n## {theme}\n")
        for ticker in tickers:
            print(f"--- {ticker} 분석 중 ---")
            try:
                full_text, signal, emoji = analyze_ticker(ta, ticker, analysis_date)
                summary.append(f"{emoji} {ticker} — {signal}")
                report.append(f"### {ticker} — {signal}\n\n{full_text}\n")
                ok += 1
            except Exception as e:                   # noqa: BLE001
                summary.append(f"⚪ {ticker} — 분석 실패")
                report.append(f"### {ticker} — 분석 실패\n\n```\n{e}\n```\n")
                fail += 1
                print(f"[ERROR] {ticker} 최종 실패: {e}")
            time.sleep(SLEEP_BETWEEN_TICKERS)
        summary.append("")

    summary.append(f"분석 완료 {ok}개 / 실패 {fail}개")
    summary.append("자세한 내용은 첨부 리포트 참고.")
    summary.append("")
    summary.append("※ 연구용 분석이며 투자 조언이 아님.")

    report_path = f"report_{analysis_date}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    send_message("\n".join(summary))
    send_document(report_path, caption=f"전체 리포트 ({analysis_date})")
    print("완료.")


if __name__ == "__main__":
    main()
