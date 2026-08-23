#!/usr/bin/env python3
"""
generate_demo.py — 生成 5 周 (W25-W29) 的演示数据。

设计思路:
- Persona: Senior 工程师 + 新手爸爸 + 学 CISSP + 用 AI 工具
- 5 周的工作 + 生活条目, 跨周 plan 追踪能命中
- 工作条目英文为主, 生活条目中文为主, 风格贴近 W30 已有的真实记录
- 重新运行会覆盖已有 demo 数据 (不会动 W30 真实数据以外的任何东西)

使用:
    python3 bin/generate_demo.py            # 生成
    python3 bin/generate_demo.py --keep     # 不覆盖已有 demo (只填补缺失周)
"""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from weekly_report import WeeklyReport, write_section  # noqa: E402

DEMO_WEEKS = [
    # ── W25 (Jun 22-28) — 暑期前 ──────────────────────────
    (
        (2026, 25),
        {
            "work": {
                "completed": [
                    "finished security audit report for client B",
                    "reviewed 2 PRs from teammates",
                    "attended Q2 OKR review meeting",
                    "started CISSP domain 2 study",
                ],
                "next_week": ["continue CISSP domain 2", "draft Q3 OKR"],
                "notes": ["client B 想要更快的报告交付周期"],
            },
            "life": {
                "completed": [
                    "周末带娃去了动物园",
                    "开始恢复晨跑 (跑了 2 次)",
                    "看完了《纳瓦尔宝典》第 5 章",
                ],
                "notes": ["晚上 11 点后不再刷手机, 已坚持一周"],
            },
        },
    ),
    # ── W26 (Jun 29 - Jul 5) ──────────────────────────────
    (
        (2026, 26),
        {
            "work": {
                "completed": [
                    "completed CISSP domain 2 (延续 W25 plan ✅)",
                    "drafted Q3 OKR (延续 W25 plan ✅)",
                    "招了 1 个实习生, 安排 onboarding",
                    "解决了 production 上的一个 race condition",
                ],
                "next_week": ["design agent prototype", "finalize Q3 OKR with manager"],
                "notes": ["race condition 修了一上午, 下次 code review 多花 5 分钟就能避免"],
            },
            "life": {
                "completed": [
                    "完成了 10km 长距离跑",
                    "跟爸妈视频",
                    "整理了家里的书柜",
                ],
                "notes": ["10km 跑完后第二天腿有点酸, 看来恢复跑还是必要的"],
            },
        },
    ),
    # ── W27 (Jul 6-12) ─────────────────────────────────────
    (
        (2026, 27),
        {
            "work": {
                "completed": [
                    "designed agent visualization prototype (延续 W26 plan ✅)",
                    "finalized Q3 OKR with manager (延续 W26 plan ✅)",
                    "onboarded 新实习生",
                    "ran security tests on production deployment",
                ],
                "next_week": ["iterate on agent prototype", "start integration with real data"],
                "notes": ["prototype over polish — 先 ship 再 polish"],
            },
            "life": {
                "completed": [
                    "hiked 香山 with family",
                    "finished 《Atomic Habits》中文版",
                    "tried a new recipe (Thai green curry)",
                ],
                "notes": ["Atomic Habits 里的 1% 改进确实在累积"],
            },
        },
    ),
    # ── W28 (Jul 13-19) ───────────────────────────────────
    (
        (2026, 28),
        {
            "work": {
                "completed": [
                    "iterated on agent prototype based on feedback (W27 plan ✅)",
                    "started integrating real data (W27 plan ✅)",
                    "reviewed intern's first PR",
                    "presented at team knowledge sharing",
                ],
                "next_week": ["finish integration", "write README + demo video"],
                "notes": ["demo video 比长篇文档更容易被同事看完"],
            },
            "life": {
                "completed": [
                    "saw 长安三万里 with family",
                    "completed 7km long run",
                    "took 2 walks during work breaks",
                ],
                "notes": ["晚上 11 点后不刷短视频又坚持了一周"],
            },
        },
    ),
    # ── W29 (Jul 20-26) — 当周 ───────────────────────────
    (
        (2026, 29),
        {
            "work": {
                "completed": [
                    "finished integration (W28 plan ✅)",
                    "wrote README + 录了 demo (W28 plan ✅)",
                    "deployed 到 staging 环境",
                    "collected feedback from 3 beta users",
                ],
                "next_week": ["ship to production", "start v2 features planning"],
                "notes": ["用户反馈里 60% 都提到了希望能加更多 visualization 选项"],
            },
            "life": {
                "completed": [
                    "周末回老家陪爸妈",
                    "开始恢复晨跑",
                    "把日记本从抽屉里又拿出来了",
                ],
                "notes": ["日记本里翻到去年写的「想当好爸爸」, 有点感慨"],
            },
        },
    ),
]


def main() -> int:
    p = argparse.ArgumentParser(description="生成 W25-W29 的演示数据")
    p.add_argument("--keep", action="store_true", help="不覆盖已有数据 (只填补缺失周)")
    args = p.parse_args()

    created = 0
    skipped = 0
    for (year, week), data in DEMO_WEEKS:
        # 已有就不动
        work_path = PROJECT_DIR / "reports" / str(year) / f"{year}-W{week:02d}-work.md"
        life_path = PROJECT_DIR / "reports" / str(year) / f"{year}-W{week:02d}-life.md"
        if args.keep and (work_path.exists() or life_path.exists()):
            print(f"  ↩ W{week:02d} 已存在, --keep 模式跳过")
            skipped += 1
            continue

        r = WeeklyReport(year=year, week=week)
        r.work.items = data["work"]["completed"]
        r.work.next_week = data["work"]["next_week"]
        r.work.notes = data["work"]["notes"]
        r.life.items = data["life"]["completed"]
        r.life.notes = data["life"]["notes"]

        w = write_section("work", r)
        life_path = write_section("life", r)
        print(f"  ✅ W{week:02d}  {w.name} | {life_path.name}")
        created += 1

    print(f"\n🎉 完成: 新建 {created} 周, 跳过 {skipped} 周")
    print("📁 现在 reports/2026/ 下共有 6 周数据 (W25-W30)")
    print("\n💡 想看汇总:")
    print("   python3 weekly_report.py summary 2026 7")
    print("   python3 weekly_report.py quarter 2026 3")
    print("   python3 weekly_report.py yearly 2026")
    return 0


if __name__ == "__main__":
    sys.exit(main())
