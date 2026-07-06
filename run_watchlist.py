#!/usr/bin/env python3
"""주간 시장 워치리스트 러너 — OpenRouter(DeepSeek 무료) / SPCX 1종목 테스트."""

import os
import sys
import time
from datetime import date, timedelta

import requests

# ════════════════════════════════════════════════════════════════
#  여기만 편집하면 됨 (EDIT HERE)
# ════════════════════════════════════════════════════════════════

WATCHLIST = {
    "테스트": ["SPCX"],
}

# OpenRouter 무료 모델 후보 (2026-07 기준 무료 + tools 지원 확인됨).
# 무료 풀은 혼잡도가 수시로 변하므로, 실행 시점에 위에서부터 살아있는
# 모델을 골라 사용함. 전부 막히면 openrouter.ai/models 에서
# Price=Free + supported_parameters=tools 필터로 목록 갱신.
MODEL_CANDIDATES = [
    "openai/gpt-oss-120b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

MAX_DEBATE_ROUNDS = 0
SLEEP_BETWEEN_TICKERS = 5

# ════════════════════════════════════════════════════════════════
#  아래부터는 건드릴 필요 없음
# ════════════════════════════════════════════════════════════════

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

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


def pick_available_model():
    """후보 목록에서 지금 응답 가능한 무료 모델을 골라 반환. 전부 막히면 None."""
    for model in MODEL_CANDIDATES:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
                timeout=60,
            )
            if r.ok:
                print(f"[INFO] 사용 모델: {model}")
                return model
            print(f"[WARN] {model} 사용 불가: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"[WARN] {model} 프로브 실패: {e}")
        time.sleep(2)
    return None


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
        except Exception as e:
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
        except Exception as e:
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
    except Exception as e:
        print(f"[WARN] 텔레그램 파일 예외: {e}")


def main():
    check_env()
    analysis_date = latest_trading_date()
    print(f"분석 기준일: {analysis_date}")

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
    except Exception as e:
        print(f"[FATAL] TradingAgents import 실패: {e}")
        send_message(f"⚠️ 워치리스트 봇: TradingAgents 임포트 실패\n{e}")
        sys.exit(1)

    model = pick_available_model()
    if not model:
        print("[FATAL] 사용 가능한 무료 모델 없음")
        send_message("⚠️ 워치리스트 봇: 무료 모델이 전부 혼잡/차단 상태입니다. 다음 실행 때 재시도합니다.")
        sys.exit(1)

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openrouter"
    config["backend_url"] = "https://openrouter.ai/api/v1"
    config["deep_think_llm"] = model
    config["quick_think_llm"] = model
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
            except Exception as e:
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
    # utf-8-sig(BOM): Windows 메모장 등에서 한글 깨짐 방지
    with open(report_path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(report))

    send_message("\n".join(summary))
    send_document(report_path, caption=f"전체 리포트 ({analysis_date})")
    print("완료.")


if __name__ == "__main__":
    main()
