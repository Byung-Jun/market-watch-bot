#!/usr/bin/env python3
"""run_watchlist 단위 테스트 — python3 -m unittest test_extract_signal"""

import unittest
from unittest import mock

import run_watchlist
from run_watchlist import extract_signal, is_rate_limit_error, pick_available_model


class TestExtractSignal(unittest.TestCase):
    # ── structured output 경로: 영어 Rating 줄 ──
    def test_english_rating_line(self):
        text = "**Rating**: Overweight\n\n**Executive Summary**: 좋아 보임"
        self.assertEqual(extract_signal(text), ("🟢", "비중확대"))

    def test_english_rating_line_hyphen(self):
        self.assertEqual(extract_signal("Rating - Sell"), ("🔴", "매도"))

    def test_english_keyword_in_body(self):
        text = "After reviewing the debate, we recommend HOLD for now."
        self.assertEqual(extract_signal(text), ("🟡", "보유"))

    # ── 자유 텍스트 폴백 경로: 한국어 응답 ──
    def test_korean_rating_line(self):
        text = "**등급**: 매수\n\n**요약**: 진입 추천"
        self.assertEqual(extract_signal(text), ("🟢", "매수"))

    def test_korean_keyword_in_body(self):
        text = "리스크 토론을 종합하면 현 시점에서는 보유가 적절합니다."
        self.assertEqual(extract_signal(text), ("🟡", "보유"))

    def test_korean_overweight_not_confused_with_buy(self):
        # "비중확대"가 "매수"보다 먼저 매칭되어야 함
        text = "매수까지는 아니고 비중확대 관점으로 접근."
        self.assertEqual(extract_signal(text), ("🟢", "비중확대"))

    def test_korean_underweight(self):
        self.assertEqual(extract_signal("등급: 비중축소"), ("🔴", "비중축소"))

    # ── 엣지 케이스 ──
    def test_no_signal(self):
        self.assertEqual(extract_signal("데이터 부족으로 결론 없음"), ("⚪", "판단불가"))

    def test_empty_and_none(self):
        self.assertEqual(extract_signal(""), ("⚪", "판단불가"))
        self.assertEqual(extract_signal(None), ("⚪", "판단불가"))


class TestIsRateLimitError(unittest.TestCase):
    def test_openrouter_429(self):
        # 2026-07-06 실제 실행에서 발생한 에러 형태
        e = Exception(
            "Error code: 429 - {'error': {'message': 'Provider returned error', "
            "'code': 429, 'metadata': {'raw': 'meta-llama/llama-3.3-70b-instruct:free "
            "is temporarily rate-limited upstream.'}}}"
        )
        self.assertTrue(is_rate_limit_error(e))

    def test_rate_limit_text(self):
        self.assertTrue(is_rate_limit_error(Exception("Rate limit exceeded")))

    def test_other_error(self):
        self.assertFalse(is_rate_limit_error(Exception("connection reset by peer")))


class TestPickAvailableModelExclude(unittest.TestCase):
    def _fake_post(self, *args, **kwargs):
        self.probed.append(kwargs["json"]["model"])
        return mock.Mock(ok=True)

    def setUp(self):
        self.probed = []

    def test_exclude_skips_candidates(self):
        first, second = run_watchlist.MODEL_CANDIDATES[:2]
        with mock.patch.object(run_watchlist.requests, "post", self._fake_post), \
             mock.patch.object(run_watchlist.time, "sleep"):
            picked = pick_available_model(exclude={first})
        self.assertEqual(picked, second)
        self.assertNotIn(first, self.probed)


if __name__ == "__main__":
    unittest.main()
