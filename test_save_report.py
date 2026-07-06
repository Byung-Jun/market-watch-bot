#!/usr/bin/env python3
"""save_reports 단위 테스트 — python3 -m unittest test_save_report"""

import json
import os
import tempfile
import unittest

from run_watchlist import save_reports


class TestSaveReports(unittest.TestCase):
    def test_save_reports_schema(self):
        collected = [
            {"ticker": "SPCX", "signal": "보유", "text": "SPCX 분석 본문"},
            {"ticker": "NVDA", "signal": "비중확대", "text": "NVDA 분석 본문"},
        ]
        with tempfile.TemporaryDirectory() as td:
            day_dir = save_reports(collected, "2026-07-05", model="m1, m2", out_dir=td)

            with open(os.path.join(day_dir, "summary.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["date"], "2026-07-05")
            self.assertEqual(data["model"], "m1, m2")
            self.assertEqual(
                data["signals"][0],
                {"ticker": "SPCX", "rating": "HOLD", "rating_ko": "보유"},
            )
            self.assertEqual(
                data["signals"][1],
                {"ticker": "NVDA", "rating": "OVERWEIGHT", "rating_ko": "비중확대"},
            )

            with open(os.path.join(day_dir, "SPCX.md"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "SPCX 분석 본문")

    def test_save_reports_unknown_rating(self):
        with tempfile.TemporaryDirectory() as td:
            day_dir = save_reports(
                [{"ticker": "X", "signal": "판단불가", "text": ""}],
                "2026-07-05", model="m", out_dir=td,
            )
            with open(os.path.join(day_dir, "summary.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["signals"][0]["rating"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
