#!/usr/bin/env python3
"""주간 시장 워치리스트 러너.

TradingAgents로 워치리스트 종목을 하나씩 분석하고,
종목별 BUY/SELL/HOLD 요약 + 전체 리포트 파일을 텔레그램으로 보낸다.
GitHub Actions에서 주 1회(일요일 밤) 자동 실행되도록 설계됨.

키(GOOGLE_API_KEY / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)는
코드에 적지 않고 GitHub Secrets에서 환경변수로 주입받는다.
"""

import os
import sys
import time
from datetime import date, timedelta

import requests

# ════════════════════════════════════════════════════════════════
#  여기만 편집하면 됨 (EDIT HERE)
# ════════════════════════════════════════════════════════════════

# 워치리스트 — 테마별로 묶음. 종목 추가/삭제는 여기서.
# 한국 주식은 .KS(코스피)/.KQ(코스닥) 접미사. 미국은 그대로.
WATCHLIST = {
    "AI": ["NVDA", "AVGO", "TSM", "GOOGL", "MSFT", "META"],
    "반도체/메모리": ["005930.KS", "000660.KS"],
    "SpaceX/우주": ["SPCX", "RKLB"],
    "방산": ["LMT", "012450.KS", "047810.KS"],
    "UAM": ["JOBY", "ACHR"],
    "멀티": ["TSLA"],
}

# 모델 — 둘 다 무료 티어 가능(2.5 Flash 계열).
# 품질 더 원하면 DEEP_THINK_MODEL만 유료 모델로 바꿔도 됨.
DEEP_THINK_MODEL = "gemini-2.5-flash"        # 추론(불/베어 토론 등)
QUICK_THINK_MODEL = "gemini-2.5-flash-lite"  # 잡일(데이터 수집 등), RPM 한도 높음
MAX_DEBATE_ROUNDS = 1                          # 토론 라운드. 늘리면 품질↑ 호출↑

# 종목 사이 대기(초). Gemini 무료 분당 한도(약 10 RPM) 완화용.
SLEEP_BETWEEN_TICKERS = 30

# ════════════════════════════════════════════════════════════════
#  아래부터는 건드릴 필요 없음
# ════════════════════════════════════════════════════════════════

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def check_env():
    missing = [n for n, v in {
        "GOOGLE_API_KEY": GOOGLE_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }.items() if not v]
    if missing:
        print(f"[FATAL] 누락된 시크릿: {', '.join(missing)}")
        sys.exit(1)


def latest_trading_date():
    """가장 최근 평일(주말이면 금요일로 롤백)."""
    d = date.today()
    while d.weekday() >= 5:   # 5=토, 6=일
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def extract_signal(text):
    """결정 텍스트에서 신호와 이모지를 추출."""
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
    """한 종목 분석. 실패 시 백오프 재시도. (전체텍스트, 신호, 이모지) 반환."""
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
            time.sleep(20 * attempt)                 # 레이트리밋 백오프
    raise last_err


def send_message(text):
    for i in range(0, len(text), 4000):              # 4096자 제한 → 분할
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
                files={"document": f},
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
    config["llm_provider"] = "google"
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
