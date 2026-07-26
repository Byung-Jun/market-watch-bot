#!/usr/bin/env python3
"""주간 시장 워치리스트 러너 — OpenRouter(DeepSeek 무료) / SPCX 1종목 테스트."""

import json
import os
import re
import sys
import time
from datetime import date, timedelta

import requests

# ════════════════════════════════════════════════════════════════
#  설정 — 종목·모델·경로는 config.json에서 편집 (코드 수정 불필요)
# ════════════════════════════════════════════════════════════════

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config.json"
)


# config.json이 없거나 깨졌을 때 쓰는 폴백 — 외부화 이전의 하드코딩 값과 동일.
# 무료 풀은 혼잡도가 수시로 변하므로, 실행 시점에 위에서부터 살아있는 모델을
# 골라 사용함. 전부 막히면 openrouter.ai/models 에서
# Price=Free + supported_parameters=tools 필터로 config.json을 갱신.
FALLBACK_CONFIG = {
    "watchlist": {
        "테스트": ["SPCX"],
    },
    "model_candidates": [
        "openai/gpt-oss-120b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ],
    "max_debate_rounds": 0,
    "sleep_between_tickers": 5,
    "reports_dir": "reports",
    "report_file_template": "report_{date}.md",
    "output_language": "Korean",
    "llm_max_retries": 5,
}


def load_config(path=None):
    """설정을 dict로 반환. 파일이 없거나 읽기 실패하면 FALLBACK_CONFIG로 폴백한다.

    경로 우선순위: 인자 path > 환경변수 WATCHLIST_CONFIG > 스크립트 옆 config.json.
    누락된 키는 FALLBACK_CONFIG 값으로 채운다.
    """
    path = path or os.environ.get("WATCHLIST_CONFIG") or DEFAULT_CONFIG_PATH
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print(f"[INFO] 설정 파일 없음({path}) — 내장 기본값으로 실행")
        cfg = {}
    except (OSError, ValueError) as e:
        print(f"[WARN] 설정 파일 읽기 실패({path}): {e} — 내장 기본값으로 실행")
        cfg = {}
    # 주석용 "_"로 시작하는 키는 무시
    cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
    return {**FALLBACK_CONFIG, **cfg}


# 모듈 레벨 상수 — 기존 임포트 경로(테스트 등) 호환용
_config = load_config()
WATCHLIST = _config["watchlist"]
MODEL_CANDIDATES = _config["model_candidates"]
MAX_DEBATE_ROUNDS = _config["max_debate_rounds"]
SLEEP_BETWEEN_TICKERS = _config["sleep_between_tickers"]

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


def is_rate_limit_error(exc):
    """무료 풀 혼잡/쿼터 초과(429) 계열 에러인지 판별."""
    s = str(exc).lower()
    return "429" in s or "rate limit" in s or "rate-limited" in s


def pick_available_model(exclude=frozenset(), candidates=None):
    """후보 목록에서 지금 응답 가능한 무료 모델을 골라 반환. 전부 막히면 None."""
    if candidates is None:
        candidates = MODEL_CANDIDATES
    for model in candidates:
        if model in exclude:
            continue
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


# TradingAgents 5단계 등급 → 이모지/한글 라벨.
# structured output이 실패하면 자유 텍스트 폴백이 한국어로 응답할 수 있어
# (output_language=Korean) 한국어 등급 단어도 함께 인식한다.
RATING_MAP = {
    "BUY": ("🟢", "매수"),
    "OVERWEIGHT": ("🟢", "비중확대"),
    "HOLD": ("🟡", "보유"),
    "UNDERWEIGHT": ("🔴", "비중축소"),
    "SELL": ("🔴", "매도"),
    "NEUTRAL": ("🟡", "중립"),
    "비중확대": ("🟢", "비중확대"),
    "비중축소": ("🔴", "비중축소"),
    "매수": ("🟢", "매수"),
    "매도": ("🔴", "매도"),
    "보유": ("🟡", "보유"),
    "중립": ("🟡", "중립"),
}

# "**Rating**: Overweight" / "Rating - Buy" 등 관대하게 매칭
RATING_LABEL_RE = re.compile(r"rating.*?[:\-][\s*]*(\w+)", re.IGNORECASE)


def extract_signal(text):
    """최종 결정문에서 5단계 등급 추출. Rating 줄 우선, 없으면 본문 키워드 스캔."""
    t = text or ""
    for line in t.splitlines():
        m = RATING_LABEL_RE.search(line)
        if m and m.group(1).upper() in RATING_MAP:
            return RATING_MAP[m.group(1).upper()]
    up = t.upper()
    # 긴/구체적인 키워드 먼저 (비중확대 안의 '매수' 오매칭 등 방지)
    for kw in ("OVERWEIGHT", "UNDERWEIGHT", "SELL", "BUY", "HOLD", "NEUTRAL",
               "비중확대", "비중축소", "매수", "매도", "보유", "중립"):
        if kw in up:
            return RATING_MAP[kw]
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
            # 무료 풀 혼잡의 Retry-After가 보통 30초 안팎이라 그보다 길게 대기
            time.sleep(40 * attempt)
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


# 한글 등급 라벨 → summary.json용 영문 코드 (premium-content 파이프라인이 소비)
KO_TO_CODE = {
    "매수": "BUY",
    "비중확대": "OVERWEIGHT",
    "보유": "HOLD",
    "비중축소": "UNDERWEIGHT",
    "매도": "SELL",
    "중립": "NEUTRAL",
    "판단불가": "UNKNOWN",
}


def save_reports(collected, analysis_date, model, out_dir="reports"):
    """premium-content 파이프라인이 읽는 구조로 리포트를 저장한다.

    reports/YYYY-MM-DD/{summary.json, <TICKER>.md}
    summary.json: {"date", "model", "signals": [{"ticker", "rating", "rating_ko"}]}
    """
    day_dir = os.path.join(out_dir, analysis_date)
    os.makedirs(day_dir, exist_ok=True)

    signals = []
    for item in collected:
        signals.append({
            "ticker": item["ticker"],
            "rating": KO_TO_CODE.get(item["signal"], "UNKNOWN"),
            "rating_ko": item["signal"],
        })
        with open(os.path.join(day_dir, f"{item['ticker']}.md"), "w", encoding="utf-8") as f:
            f.write(item["text"])

    with open(os.path.join(day_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"date": analysis_date, "model": model, "signals": signals},
            f, ensure_ascii=False, indent=2,
        )
    return day_dir


def main(config=None, config_path=None):
    """워치리스트 실행. config(dict)를 주입하거나 config_path로 로드 (기본: config.json)."""
    cfg = config if config is not None else load_config(config_path)
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

    model = pick_available_model(candidates=cfg["model_candidates"])
    if not model:
        print("[FATAL] 사용 가능한 무료 모델 없음")
        send_message("⚠️ 워치리스트 봇: 무료 모델이 전부 혼잡/차단 상태입니다. 다음 실행 때 재시도합니다.")
        sys.exit(1)

    def make_graph(m):
        ta_config = DEFAULT_CONFIG.copy()
        ta_config["llm_provider"] = "openrouter"
        ta_config["backend_url"] = "https://openrouter.ai/api/v1"
        ta_config["deep_think_llm"] = m
        ta_config["quick_think_llm"] = m
        ta_config["max_debate_rounds"] = cfg["max_debate_rounds"]
        ta_config["online_tools"] = True
        ta_config["output_language"] = cfg["output_language"]  # 리포트 본문 언어 (등급 줄은 영어 고정)
        # SDK 레벨 재시도 — Retry-After를 존중하므로 무료 풀 혼잡(429)을 견딤
        ta_config["llm_max_retries"] = cfg["llm_max_retries"]
        return TradingAgentsGraph(debug=False, config=ta_config)

    ta = make_graph(model)
    tried_models = {model}

    summary = [f"📊 주간 시장 리포트 ({analysis_date} 기준)", ""]
    report = [f"# 주간 시장 리포트 ({analysis_date} 기준)\n"]
    collected = []  # save_reports용 — 분석 성공 종목만 담는다
    ok = fail = 0

    for theme, tickers in cfg["watchlist"].items():
        summary.append(f"[{theme}]")
        report.append(f"\n## {theme}\n")
        for ticker in tickers:
            print(f"--- {ticker} 분석 중 ---")
            err = None
            # 현재 모델로 시도하고, 무료 풀 혼잡(429)이 계속되면
            # 아직 안 써본 후보 모델로 갈아타며 재시도
            while True:
                try:
                    full_text, signal, emoji = analyze_ticker(ta, ticker, analysis_date)
                    err = None
                    break
                except Exception as e:
                    err = e
                    if not is_rate_limit_error(e):
                        break
                    alt = pick_available_model(exclude=tried_models, candidates=cfg["model_candidates"])
                    if not alt:
                        break
                    print(f"[INFO] 무료 풀 혼잡 → 모델 교체 후 재시도: {alt}")
                    tried_models.add(alt)
                    ta = make_graph(alt)
            if err is None:
                summary.append(f"{emoji} {ticker} — {signal}")
                report.append(f"### {ticker} — {signal}\n\n{full_text}\n")
                collected.append({"ticker": ticker, "signal": signal, "text": full_text})
                ok += 1
            else:
                summary.append(f"⚪ {ticker} — 분석 실패")
                report.append(f"### {ticker} — 분석 실패\n\n```\n{err}\n```\n")
                fail += 1
                print(f"[ERROR] {ticker} 최종 실패: {err}")
            time.sleep(cfg["sleep_between_tickers"])
        summary.append("")

    summary.append(f"분석 완료 {ok}개 / 실패 {fail}개")
    summary.append("자세한 내용은 첨부 리포트 참고.")
    summary.append("")
    summary.append("※ 연구용 분석이며 투자 조언이 아님.")

    report_path = cfg["report_file_template"].format(date=analysis_date)
    # utf-8-sig(BOM): Windows 메모장 등에서 한글 깨짐 방지
    with open(report_path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(report))

    if collected:
        day_dir = save_reports(
            collected, analysis_date,
            model=", ".join(sorted(tried_models)),
            out_dir=cfg["reports_dir"],
        )
        print(f"리포트 저장: {day_dir}")

    send_message("\n".join(summary))
    send_document(report_path, caption=f"전체 리포트 ({analysis_date})")
    print("완료.")


if __name__ == "__main__":
    main()
