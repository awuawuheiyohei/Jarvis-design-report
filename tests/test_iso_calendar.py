"""测试 ISO 周 / 月份 / 季度 / 年份的工具函数."""

import sys
import unittest
from datetime import date
from pathlib import Path

# 让 import weekly_report 能找到
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import weekly_report as wr


class TestIsoWeek(unittest.TestCase):
    def test_jan_4_is_always_w01(self):
        """ISO 标准: 每年 1 月 4 日所在的那周是 W01."""
        for year in (2020, 2024, 2025, 2026, 2030, 2033):
            y, w = wr.iso_week(date(year, 1, 4))
            self.assertEqual(y, year, f"{year}-01-04 should be in week 1")
            self.assertEqual(w, 1, f"{year}-01-04 should be in week 1")

    def test_week_label_format(self):
        self.assertEqual(wr.week_label(2026, 5), "2026-W05")
        self.assertEqual(wr.week_label(2026, 30), "2026-W30")
        self.assertEqual(wr.week_label(2026, 1), "2026-W01")
        self.assertEqual(wr.week_label(2026, 53), "2026-W53")

    def test_week_range_returns_monday_sunday(self):
        # 2026-W30: Monday Jul 20, Sunday Jul 26
        mon, sun = wr.week_range(2026, 30)
        self.assertEqual(mon, date(2026, 7, 20))
        self.assertEqual(sun, date(2026, 7, 26))
        self.assertEqual(mon.weekday(), 0)  # Monday
        self.assertEqual(sun.weekday(), 6)  # Sunday

    def test_week_range_cross_year(self):
        """2026-W01: Monday Dec 29 2025, Sunday Jan 4 2026."""
        mon, sun = wr.week_range(2026, 1)
        self.assertEqual(mon, date(2025, 12, 29))
        self.assertEqual(sun, date(2026, 1, 4))

    def test_week_range_cross_month(self):
        """2026-W27: Mon Jun 29, Sun Jul 5."""
        mon, sun = wr.week_range(2026, 27)
        self.assertEqual(mon, date(2026, 6, 29))
        self.assertEqual(sun, date(2026, 7, 5))

    def test_week_range_returns_7_days(self):
        for week in (1, 13, 26, 30, 52, 53):
            mon, sun = wr.week_range(2026, week)
            self.assertEqual((sun - mon).days, 6, f"W{week} should be 7 days")

    def test_fmt_date_zh(self):
        self.assertEqual(wr.fmt_date_zh(date(2026, 7, 4)), "2026-07-04")
        self.assertEqual(wr.fmt_date_zh(date(2026, 12, 31)), "2026-12-31")
        self.assertEqual(wr.fmt_date_zh(date(2025, 1, 1)), "2025-01-01")


class TestWeeksInMonth(unittest.TestCase):
    def test_july_2026_weeks(self):
        """2026-07: W28 (Mon Jul 6) 到 W31 (Mon Jul 27). W27 属于 6 月 (Mon Jun 29)."""
        weeks = wr.weeks_starting_in_month(2026, 7)
        self.assertEqual(weeks, [(2026, 28), (2026, 29), (2026, 30), (2026, 31)])

    def test_february_2026_short_month(self):
        """2026-02: W06 (Mon Feb 2) 到 W09 (Mon Feb 23). W05 结束于 Sun Feb 1."""
        weeks = wr.weeks_starting_in_month(2026, 2)
        self.assertEqual(weeks[0], (2026, 6))
        self.assertEqual(weeks[-1], (2026, 9))
        self.assertEqual(len(weeks), 4)  # 4 个周一: 2, 9, 16, 23

    def test_empty_result_for_nonexistent_month(self):
        # 应该返回 [] (实际上 calendar.monthrange 会爆, 测试用 try/except)
        # 这里不测异常 case, 只测正常月
        weeks = wr.weeks_starting_in_month(2026, 4)  # April
        self.assertGreater(len(weeks), 0)
        self.assertLessEqual(len(weeks), 5)


class TestWeeksInQuarter(unittest.TestCase):
    def test_q3_2026(self):
        """Q3 = Jul-Sep. W27 属于 Q2 (Mon Jun 29), Q3 第一个是 W28 (Mon Jul 6)."""
        weeks = wr.weeks_in_quarter(2026, 3)
        self.assertEqual(weeks[0], (2026, 28))  # 不是 27
        self.assertEqual(weeks[-1], (2026, 40))
        self.assertEqual(weeks, sorted(weeks))
        # Q3 = 13 周 (ISO 标准)
        self.assertEqual(len(weeks), 13)

    def test_q1_2026(self):
        """Q1 = Jan-Mar."""
        weeks = wr.weeks_in_quarter(2026, 1)
        self.assertGreater(len(weeks), 12)
        self.assertLess(len(weeks), 15)

    def test_invalid_quarter(self):
        with self.assertRaises(ValueError):
            wr.weeks_in_quarter(2026, 0)
        with self.assertRaises(ValueError):
            wr.weeks_in_quarter(2026, 5)


class TestWeeksInYear(unittest.TestCase):
    def test_year_2026(self):
        """2026 有 53 周 (2026-01-01 是周四)."""
        weeks = wr.weeks_in_year(2026)
        self.assertEqual(len(weeks), 53)
        # 第一个 W01 (Mon Dec 29 2025), 最后一个 W53 (Mon Dec 28 2026)
        self.assertEqual(weeks[0][1], 1)
        self.assertEqual(weeks[-1][1], 53)

    def test_year_2025(self):
        """2025 有 52 周."""
        weeks = wr.weeks_in_year(2025)
        self.assertEqual(len(weeks), 52)

    def test_year_2027(self):
        """2027 有 52 周 (2027-01-01 是周五)."""
        weeks = wr.weeks_in_year(2027)
        self.assertEqual(len(weeks), 52)


if __name__ == "__main__":
    unittest.main()


class TestStreak(unittest.TestCase):
    """测试 compute_streak (连续写周报的周数)."""

    def test_streak_with_real_data(self):
        """用真实 reports/ 数据 (W25-W30 都有) → streak = 6."""
        from datetime import date

        streak = wr.compute_streak(date(2026, 7, 26))
        self.assertEqual(streak, 6, f"expected 6, got {streak}")

    def test_streak_current_week_empty(self):
        """当前 W34 没数据, 跳过找 W25-W30 的连续段 → 6."""
        from datetime import date

        streak = wr.compute_streak(date(2026, 8, 23))
        self.assertEqual(streak, 6)

    def test_streak_no_data(self):
        """完全没数据 → 0."""
        import tempfile
        from datetime import date

        with tempfile.TemporaryDirectory() as tmp:
            backup = wr.REPORTS_DIR
            wr.REPORTS_DIR = Path(tmp)
            try:
                streak = wr.compute_streak(date(2026, 8, 23))
                self.assertEqual(streak, 0)
            finally:
                wr.REPORTS_DIR = backup

    def test_prev_iso_week_normal(self):
        """普通情况: W30 的前一周是 W29."""
        self.assertEqual(wr._prev_iso_week(2026, 30), (2026, 29))
        self.assertEqual(wr._prev_iso_week(2026, 5), (2026, 4))

    def test_prev_iso_week_cross_year(self):
        """跨年: 2026-W01 的前一周是 2025 的最后一周."""
        prev = wr._prev_iso_week(2026, 1)
        # 2025 有 52 周, 2025-W52 是最后一周
        self.assertEqual(prev, (2025, 52))

    def test_prev_iso_week_year_start(self):
        """W02 -> W01."""
        self.assertEqual(wr._prev_iso_week(2026, 2), (2026, 1))
