"""测试 parse_section / write_section / read_section / report_path."""
import unittest
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import weekly_report as wr


class TestParseSection(unittest.TestCase):
    def test_parse_work_section_with_all_three(self):
        raw = """# 工作周报 · 2026-W30

> 周期：2026-07-20 (周一) ~ 2026-07-26 (周日)

## ✅ 本周完成
- 完成 X
- 完成 Y

## 🚀 下周计划
- 计划 A
- 计划 B

## 💡 心得 / 反思
- 心得 1
"""
        result = wr.parse_section(raw)
        self.assertEqual(result["completed"], ["完成 X", "完成 Y"])
        self.assertEqual(result["next_week"], ["计划 A", "计划 B"])
        self.assertEqual(result["notes"], ["心得 1"])

    def test_parse_empty_section(self):
        result = wr.parse_section(None)
        self.assertEqual(result, {"completed": [], "next_week": [], "notes": []})

    def test_parse_section_with_no_plans_or_notes(self):
        raw = """# 工作周报 · 2026-W30

## ✅ 本周完成
- 完成 X

## 🚀 下周计划
_(空)_

## 💡 心得 / 反思
_(空)_
"""
        result = wr.parse_section(raw)
        self.assertEqual(result["completed"], ["完成 X"])
        self.assertEqual(result["next_week"], [])
        self.assertEqual(result["notes"], [])

    def test_parse_section_with_blank_lines(self):
        raw = """## ✅ 本周完成
- 项目 A
- 项目 B

## 🚀 下周计划
- 计划 X
"""
        result = wr.parse_section(raw)
        self.assertEqual(result["completed"], ["项目 A", "项目 B"])
        self.assertEqual(result["next_week"], ["计划 X"])


class TestWriteReadRoundtrip(unittest.TestCase):
    """write_section 写出的文件, parse_section 应该能完整读回."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_reports = wr.REPORTS_DIR
        wr.REPORTS_DIR = Path(self.tmpdir)

    def tearDown(self):
        wr.REPORTS_DIR = self.original_reports
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_roundtrip_work_section(self):
        r = wr.WeeklyReport(year=2026, week=30)
        r.work.items = ["完成功能 A", "修了 bug B"]
        r.work.next_week = ["写文档"]
        r.work.notes = ["复盘: mock 数据更快"]
        path = wr.write_section("work", r)
        self.assertTrue(path.exists())
        # Round-trip
        read_back = wr.parse_section(path.read_text(encoding="utf-8"))
        self.assertEqual(read_back["completed"], ["完成功能 A", "修了 bug B"])
        self.assertEqual(read_back["next_week"], ["写文档"])
        self.assertEqual(read_back["notes"], ["复盘: mock 数据更快"])

    def test_roundtrip_life_section_with_chinese(self):
        r = wr.WeeklyReport(year=2026, week=30)
        r.life.items = ["去了香山", "跑了 5km"]
        r.life.notes = ["开始用日记本"]
        path = wr.write_section("life", r)
        read_back = wr.parse_section(path.read_text(encoding="utf-8"))
        self.assertEqual(read_back["completed"], ["去了香山", "跑了 5km"])
        self.assertEqual(read_back["notes"], ["开始用日记本"])

    def test_roundtrip_unicode_emoji(self):
        r = wr.WeeklyReport(year=2026, week=30)
        r.work.items = ["🚀 launched feature", "📝 wrote docs"]
        path = wr.write_section("work", r)
        read_back = wr.parse_section(path.read_text(encoding="utf-8"))
        self.assertEqual(read_back["completed"], ["🚀 launched feature", "📝 wrote docs"])


class TestReportPath(unittest.TestCase):
    def test_work_path(self):
        p = wr.report_path("work", 2026, 30)
        self.assertEqual(p.name, "2026-W30-work.md")
        self.assertEqual(p.parent.name, "2026")

    def test_life_path(self):
        p = wr.report_path("life", 2026, 1)
        self.assertEqual(p.name, "2026-W01-life.md")

    def test_invalid_category(self):
        with self.assertRaises(ValueError):
            wr.report_path("invalid", 2026, 30)


if __name__ == "__main__":
    unittest.main()
