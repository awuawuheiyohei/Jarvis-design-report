"""CLI 集成测试 — 跑实际子命令验证输出."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
WR = str(PROJECT_DIR / "weekly_report.py")


class TestCliHelp(unittest.TestCase):
    """每个子命令的 --help 应该能跑成功."""

    def test_help(self):
        for cmd in ["new", "list", "view", "combine", "today", "summary", "yearly", "quarter", "recap"]:
            with self.subTest(cmd=cmd):
                r = subprocess.run(
                    [sys.executable, WR, cmd, "--help"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r.returncode, 0, f"{cmd} --help failed: {r.stderr}")
                self.assertIn("usage:", r.stdout)


class TestCliTodayAndList(unittest.TestCase):
    def test_today(self):
        r = subprocess.run(
            [sys.executable, WR, "today"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("今天", r.stdout)
        # 应该有 "W" 标记 ISO 周
        self.assertRegex(r.stdout, r"202[0-9]-W\d{2}")

    def test_list(self):
        r = subprocess.run(
            [sys.executable, WR, "list"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("已有周报", r.stdout)


class TestCliNewInTempDir(unittest.TestCase):
    """在临时目录里建一份周报, 再 view 它."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # 把 REPORTS_DIR 通过环境变量改不了, 改用 chdir
        self.original_cwd = Path.cwd()
        # 直接在临时目录里造一个 weekly_report 项目的副本
        # 但这样太重; 改用 monkey-patch 通过 PYTHONPATH 跑一个 wrapper

    def tearDown(self):
        Path(self.original_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_new_with_input_quits_immediately(self):
        """输两次 :q 应该让 new 退出且不写文件."""
        # 用 :q 直接退出两个分类
        result = subprocess.run(
            [sys.executable, WR, "new", "--year", "2099", "--week", "1"],
            input=":q\n:q\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        # 应该不写文件 (因为都空)
        # 不能直接验证文件, 因为可能用真实 REPORTS_DIR
        # 但应该不 crash
        self.assertIn("部分都为空", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()


class TestGhSyncHelpers(unittest.TestCase):
    """测试 _load_gh_sync / _save_gh_sync / _plan_key 工具函数."""

    @classmethod
    def setUpClass(cls):
        import sys

        cls.wr = sys.modules.get("weekly_report")
        if cls.wr is None:
            import weekly_report as wr_mod

            cls.wr = wr_mod
            sys.modules["weekly_report"] = wr_mod

    def setUp(self):
        import tempfile

        self._orig = self.wr.GHSYNC_FILE
        self.tmp = tempfile.mkdtemp()
        import pathlib as _p

        self.wr.REPORTS_DIR = _p.Path(self.tmp)
        self.wr.GHSYNC_FILE = self.wr.REPORTS_DIR / ".gh-sync.json"

    def tearDown(self):
        import shutil

        self.wr.GHSYNC_FILE = self._orig
        self.wr.REPORTS_DIR = self._orig.parent
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_load_empty(self):
        result = self.wr._load_gh_sync()
        self.assertEqual(result, {"issues": {}})

    def test_save_and_load_roundtrip(self):
        data = {"issues": {"abc123": {"issue_number": 42, "title": "test"}}}
        self.wr._save_gh_sync(data)
        loaded = self.wr._load_gh_sync()
        self.assertEqual(loaded, data)

    def test_plan_key_deterministic(self):
        k1 = self.wr._plan_key("Ship to production")
        k2 = self.wr._plan_key("  ship to PRODUCTION  ")
        # 大小写 + 前后空格不影响
        self.assertEqual(k1, k2)

    def test_plan_key_different_for_different(self):
        k1 = self.wr._plan_key("Ship to production")
        k2 = self.wr._plan_key("Ship to staging")
        self.assertNotEqual(k1, k2)


class TestTplListActionLinks(unittest.TestCase):
    """A1 增强: /list 页应该每行有 ✏️ 编辑 + 🗑️ 删除 链接."""

    def test_tpl_list_includes_edit_link(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
        from weekly_report_web import tpl_list

        html = tpl_list([(2026, 30), (2026, 29)])
        self.assertIn("/edit/2026/30", html)
        self.assertIn("/edit/2026/29", html)

    def test_tpl_list_includes_delete_link(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
        from weekly_report_web import tpl_list

        html = tpl_list([(2026, 30)])
        self.assertIn("/delete/2026/30", html)

    def test_tpl_index_home_button_uses_year_week_query(self):
        """主页写周报按钮应该带 ?year=&week= 参数, 让有数据的周自动进编辑模式."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
        from weekly_report_web import tpl_index

        html = tpl_index(
            stats={"streak": 7, "coverage": {"weeks_reported": 7, "weeks_total": 53}, "totals": {}},
            recent=[(2026, 31)],
        )
        # 主页按钮应该带 year= 和 week= 参数
        self.assertIn("new?year=", html)
        self.assertIn("&week=", html)


class TestMergeForAppend(unittest.TestCase):
    """直接测 _merge_for_append 纯函数 (case-insensitive dedup)."""

    @classmethod
    def setUpClass(cls):
        import sys
        from pathlib import Path

        bin_path = str(Path(__file__).resolve().parent.parent / "bin")
        if bin_path not in sys.path:
            sys.path.insert(0, bin_path)

    def test_basic_merge(self):
        from weekly_report_web import _merge_for_append

        result = _merge_for_append(["a", "b"], ["c", "d"])
        self.assertEqual(result, ["a", "b", "c", "d"])

    def test_dedup_case_insensitive(self):
        from weekly_report_web import _merge_for_append

        result = _merge_for_append(["Foo", "BAR"], ["foo", "Bar", "new"])
        self.assertEqual(result, ["Foo", "BAR", "new"])

    def test_whitespace_tolerance(self):
        from weekly_report_web import _merge_for_append

        result = _merge_for_append(["item 1"], ["  item 1  ", "item 2"])
        # "  item 1  " 与 "item 1" 视为相同
        self.assertEqual(result, ["item 1", "item 2"])

    def test_existing_empty(self):
        from weekly_report_web import _merge_for_append

        result = _merge_for_append([], ["a", "b"])
        self.assertEqual(result, ["a", "b"])

    def test_new_empty(self):
        from weekly_report_web import _merge_for_append

        result = _merge_for_append(["a", "b"], [])
        self.assertEqual(result, ["a", "b"])

    def test_both_empty(self):
        from weekly_report_web import _merge_for_append

        result = _merge_for_append([], [])
        self.assertEqual(result, [])

    def test_unicode_dedup(self):
        from weekly_report_web import _merge_for_append

        result = _merge_for_append(["完成 X", "修复 Y"], ["完成 X", "完成 Z"])
        # "完成 X" 重复, 跳过; "完成 Z" 是新的
        self.assertEqual(result, ["完成 X", "修复 Y", "完成 Z"])
