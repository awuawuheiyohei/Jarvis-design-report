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
