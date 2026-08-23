#!/usr/bin/env python3
"""
weekly_report.py — 生活 / 工作 分开的周报工具

特性:
- 交互式输入，按周自动归档为 Markdown 文件
- 生活 / 工作 两个分类，支持多条条目（一句一行）
- 可选 「下周计划」「心得/反思」
- 命令: new / list / view / combine / today
- 零依赖，纯标准库
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

REPORTS_DIR = Path(__file__).parent / "reports"


# ---------- 时间与归档 ----------


def iso_week(d: date) -> tuple[int, int]:
    """返回 (年, ISO 周数)。ISO 周一是一周的第一天。"""
    iso = d.isocalendar()
    return iso.year, iso.week


def week_range(year: int, week: int) -> tuple[date, date]:
    """返回给定 ISO 周的周一到周日日期。"""
    fourth_jan = date(year, 1, 4)
    fourth_jan_iso = fourth_jan.isocalendar()
    week1_monday = fourth_jan - timedelta(days=fourth_jan_iso.weekday - 1)
    monday = week1_monday + timedelta(weeks=week - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def fmt_date_zh(d: date) -> str:
    return f"{d.year}-{d.month:02d}-{d.day:02d}"


def week_label(year: int, week: int) -> str:
    return f"{year}-W{week:02d}"


# ---------- 交互输入 ----------


@dataclass
class ReportSection:
    title: str
    items: list[str] = field(default_factory=list)
    next_week: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class WeeklyReport:
    year: int
    week: int
    work: ReportSection = field(default_factory=lambda: ReportSection("工作"))
    life: ReportSection = field(default_factory=lambda: ReportSection("生活"))


def prompt_section(section: ReportSection) -> None:
    """交互式录入一个分类（多条，空行结束）。"""
    print(f"\n📝 录入【{section.title}】")
    print("   - 一行一条，回车确认；连续两次回车结束。")
    print("   - 单行输入 ':n' 进入【下周计划】，':r' 进入【心得/反思】，':q' 结束。")
    print()

    target = section.items
    while True:
        try:
            line = input(f"  [{section.title} #{len(target) + 1}] ").rstrip()
        except EOFError:
            print()
            break

        if line == ":q":
            break
        if line == "":
            if target:
                break
            continue
        if line == ":n":
            target = section.next_week
            print("   ↳ 已切换到【下周计划】")
            continue
        if line == ":r":
            target = section.notes
            print("   ↳ 已切换到【心得/反思】")
            continue
        target.append(line)


# ---------- 文件 I/O ----------


def report_path(category: str, year: int, week: int) -> Path:
    if category not in ("life", "work"):
        raise ValueError("category 必须是 life 或 work")
    folder = REPORTS_DIR / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{week_label(year, week)}-{category}.md"


def write_section(category: str, report: WeeklyReport) -> Path:
    section = report.life if category == "life" else report.work
    monday, sunday = week_range(report.year, report.week)

    lines: list[str] = []
    lines.append(f"# {section.title}周报 · {week_label(report.year, report.week)}")
    lines.append("")
    lines.append(f"> 周期：{fmt_date_zh(monday)} (周一) ~ {fmt_date_zh(sunday)} (周日)")
    lines.append(f"> 录入时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## ✅ 本周完成")
    if section.items:
        for it in section.items:
            lines.append(f"- {it}")
    else:
        lines.append("_(空)_")
    lines.append("")
    lines.append("## 🚀 下周计划")
    if section.next_week:
        for it in section.next_week:
            lines.append(f"- {it}")
    else:
        lines.append("_(空)_")
    lines.append("")
    lines.append("## 💡 心得 / 反思")
    if section.notes:
        for it in section.notes:
            lines.append(f"- {it}")
    else:
        lines.append("_(空)_")
    lines.append("")

    path = report_path(category, report.year, report.week)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def read_section(category: str, year: int, week: int) -> str | None:
    path = report_path(category, year, week)
    return path.read_text(encoding="utf-8") if path.exists() else None


# ---------- 子命令 ----------


def cmd_new(args: argparse.Namespace) -> int:
    today = date.today()
    if args.year is None:
        year, week = iso_week(today)
    else:
        year, week = args.year, args.week

    r = WeeklyReport(year=year, week=week)
    monday, sunday = week_range(year, week)
    print(f"📅 本次写入：{week_label(year, week)}  ({fmt_date_zh(monday)} ~ {fmt_date_zh(sunday)})")
    print("   提示：Ctrl+C 可随时退出，已保存的部分不会丢失。")

    try:
        if not args.skip_work:
            prompt_section(r.work)
        if not args.skip_life:
            prompt_section(r.life)
    except KeyboardInterrupt:
        print("\n⚠️  中断，未保存任何文件。")
        return 130

    saved: list[Path] = []
    if r.work.items or r.work.next_week or r.work.notes:
        saved.append(write_section("work", r))
    else:
        print("⏭  工作部分为空，跳过保存。")

    if r.life.items or r.life.next_week or r.life.notes:
        saved.append(write_section("life", r))
    else:
        print("⏭  生活部分为空，跳过保存。")

    if saved:
        print("\n✅ 已保存：")
        for p in saved:
            print(f"   - {p}")
    else:
        print("\nℹ️  两部分都为空，没有生成文件。")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    if not REPORTS_DIR.exists():
        print("还没有任何周报。试试 ")
        return 0
    print("📚 已有周报：")
    for year_dir in sorted(REPORTS_DIR.iterdir()):
        if not year_dir.is_dir():
            continue
        for f in sorted(year_dir.glob("*-" + "*.md")):
            print(f"   {f.relative_to(REPORTS_DIR)}")
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    year, week = args.year, args.week
    label = week_label(year, week)
    work = read_section("work", year, week)
    life = read_section("life", year, week)
    if not work and not life:
        print(f"❌ 未找到 {label} 的周报。")
        return 1
    if work:
        print(f"\n===== 🗂  {label} · 工作 =====")
        print(work)
    if life:
        print(f"===== 🗂  {label} · 生活 =====")
        print(life)
    return 0


def cmd_combine(args: argparse.Namespace) -> int:
    year, week = args.year, args.week
    label = week_label(year, week)
    work = read_section("work", year, week)
    life = read_section("life", year, week)
    if not work and not life:
        print(f"❌ 未找到 {label} 的周报，无法合并。")
        return 1
    monday, sunday = week_range(year, week)
    parts: list[str] = []
    parts.append(f"# {label} 周报合并版  ({fmt_date_zh(monday)} ~ {fmt_date_zh(sunday)})")
    parts.append("")
    if work:
        parts.append(work.rstrip())
    if life:
        parts.append(life.rstrip())
    out = REPORTS_DIR / str(year) / f"{label}-combined.md"
    out.write_text("\n\n---\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"✅ 已合并：{out}")
    return 0


def cmd_today(_args: argparse.Namespace) -> int:
    y, w = iso_week(date.today())
    monday, sunday = week_range(y, w)
    print(f"今天：{date.today().isoformat()}")
    print(f"属于：{week_label(y, w)}  ({fmt_date_zh(monday)} ~ {fmt_date_zh(sunday)})")
    print(f"距离本周结束还有：{(sunday - date.today()).days} 天")
    return 0


# ---------- 月度汇总 ----------


def weeks_starting_in_month(year: int, month: int) -> list[tuple[int, int]]:
    """返回 (iso_year, iso_week)，包含所有「周一落在 (year, month) 内」的周。"""
    _, last_day = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    seen: set[tuple[int, int]] = set()
    weeks: list[tuple[int, int]] = []
    cur = start
    while cur <= end:
        key = iso_week(cur)
        if key not in seen:
            seen.add(key)
            weeks.append(key)
        cur += timedelta(days=1)
    weeks.sort()
    return weeks


def parse_section(raw: str | None) -> dict[str, list[str]]:
    """把 write_section 产出的 markdown 反解为 dict。"""
    out: dict[str, list[str]] = {"completed": [], "next_week": [], "notes": []}
    if not raw:
        return out
    for chunk in raw.split("\n## ")[1:]:
        header, _, body = chunk.partition("\n")
        items: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(stripped[2:])
            elif stripped == "_(空)_":
                pass
        if "本周完成" in header:
            out["completed"] = items
        elif "下周计划" in header:
            out["next_week"] = items
        elif "心得" in header:
            out["notes"] = items
    return out


def render_summary_markdown(year: int, month: int, weeks_data: list[dict]) -> Path:
    lines: list[str] = []
    lines.append(f"# {year} 年 {month} 月 · 月度汇总")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(
        f"> 覆盖：{len(weeks_data)} 周 ({week_label(weeks_data[0]['year'], weeks_data[0]['week'])} ~ {week_label(weeks_data[-1]['year'], weeks_data[-1]['week'])})"
    )
    lines.append("")

    lines.append("## 📅 涉及周次")
    for w in weeks_data:
        monday, sunday = week_range(w["year"], w["week"])
        lines.append(f"- **{week_label(w['year'], w['week'])}**  ({fmt_date_zh(monday)} ~ {fmt_date_zh(sunday)})")
    lines.append("")

    def _dump_section(heading: str, key: str, weeks: list[dict]) -> None:
        lines.append(f"## {heading}")
        any_block = False
        for w in weeks:
            items = w[key]
            if items:
                any_block = True
                lines.append(f"### {week_label(w['year'], w['week'])}")
                for it in items:
                    lines.append(f"- {it}")
                lines.append("")
        if not any_block:
            lines.append("_(本月无相关条目)_")
            lines.append("")

    _dump_section("💼 工作 · 本月完成", "work_completed_pre", weeks_data)
    _dump_section("🎯 工作 · 当初规划的下周计划", "work_next_pre", weeks_data)
    _dump_section("🌿 生活 · 本月完成", "life_completed_pre", weeks_data)
    _dump_section("💡 心得 / 反思", "notes_pre", weeks_data)

    total_work = sum(len(w["work"]["completed"]) for w in weeks_data)
    total_life = sum(len(w["life"]["completed"]) for w in weeks_data)
    total_work_notes = sum(len(w["work"]["notes"]) for w in weeks_data)
    total_life_notes = sum(len(w["life"]["notes"]) for w in weeks_data)
    total_next = sum(len(w["work"]["next_week"]) for w in weeks_data)

    lines.append("## 📊 月度数据")
    lines.append(f"- 工作完成：**{total_work}** 条")
    lines.append(f"- 生活完成：**{total_life}** 条")
    lines.append(f"- 下周规划：**{total_next}** 条")
    lines.append(f"- 工作心得：**{total_work_notes}** 条")
    lines.append(f"- 生活心得：**{total_life_notes}** 条")
    lines.append(f"- 涉及周数：**{len(weeks_data)}** 周")
    lines.append("")

    out = REPORTS_DIR / str(year) / f"{year}-{month:02d}-summary.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def cmd_summary(args: argparse.Namespace) -> int:
    year, month = args.year, args.month
    if not (1 <= month <= 12):
        print("❌ 月份必须在 1-12 之间")
        return 1

    weeks = weeks_starting_in_month(year, month)

    weeks_data: list[dict] = []
    missing: list[str] = []
    for wy, ww in weeks:
        work_path = report_path("work", wy, ww)
        life_path = report_path("life", wy, ww)
        work_raw = work_path.read_text(encoding="utf-8") if work_path.exists() else None
        life_raw = life_path.read_text(encoding="utf-8") if life_path.exists() else None
        if work_raw or life_raw:
            work_p = parse_section(work_raw)
            life_p = parse_section(life_raw)
            notes_combined = work_p["notes"] + life_p["notes"]
            weeks_data.append(
                {
                    "year": wy,
                    "week": ww,
                    "work": work_p,
                    "life": life_p,
                    "work_completed_pre": work_p["completed"],
                    "work_next_pre": work_p["next_week"],
                    "life_completed_pre": life_p["completed"],
                    "notes_pre": notes_combined,
                }
            )
        else:
            missing.append(week_label(wy, ww))

    if not weeks_data:
        print(f"❌ {year}-{month:02d} 没有可汇总的周报（理论涉及 {len(weeks)} 周）。")
        if missing:
            print(f"   缺失周次：{', '.join(missing)}")
            print("   用 `wr new --year YYYY --week WW` 补录后再次汇总。")
        return 1

    if args.format == "json":
        import json

        payload = {
            "year": year,
            "month": month,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "weeks": weeks_data,
            "missing_weeks": missing,
        }
        out = REPORTS_DIR / str(year) / f"{year}-{month:02d}-summary.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ JSON 已生成：{out}")
        if missing:
            print(f"   ⚠️  缺失：{', '.join(missing)}")
        return 0

    out = render_summary_markdown(year, month, weeks_data)
    print(f"✅ 月度汇总已生成：{out}")
    if missing:
        print(f"   ⚠️  缺失：{', '.join(missing)}（补录后再跑一次 `wr summary` 即可重生成）")
    return 0


# ---------- 年度汇总 ----------


def weeks_in_year(year: int) -> list[tuple[int, int]]:
    """返回 [year-01-01, year-12-31] 范围内所有 ISO 周 (iso_year, iso_week)，去重排序。"""
    weeks: set[tuple[int, int]] = set()
    for month in range(1, 13):
        for w in weeks_starting_in_month(year, month):
            weeks.add(w)
    return sorted(weeks)


def _is_significant_chunk(chunk: str) -> bool:
    """判断一个拆出来的字串是否足以作为匹配关键字。
    - 纯 CJK: 长度 ≥ 2
    - 含 ASCII/数字: 长度 ≥ 3
    """
    if not chunk:
        return False
    is_cjk = all("\u4e00" <= c <= "\u9fff" for c in chunk)
    return (len(chunk) >= 2) if is_cjk else (len(chunk) >= 3)


def _plan_chunks(text: str) -> list[str]:
    """把字符串拆成可单独匹配的关键字 (按空白 / 中英文常见标点切)。"""
    return [c.strip() for c in re.split(r"[\s,，。、;；:：()（）【】\[\]/]+", text.lower()) if c.strip()]


def _track_plans(weeks_data: list[dict]) -> tuple[list[dict], list[dict]]:
    """两层匹配:
    1) 完整子串 (保守): plan 完整出现在 done 里, 或反过来
    2) 关键字命中 (宽松): 按标点/空白拆 plan, 任一有效 chunk 出现在 done 里

    返回 (open_plans, closed_plans)。太短 (纯文本 < 4 字符) 直接进 pending。
    """
    open_plans: list[dict] = []
    closed_plans: list[dict] = []
    for i, w in enumerate(weeks_data):
        for plan in w["work"]["next_week"]:
            raw = plan.strip()
            if len(raw) < 4:
                open_plans.append({"from_week": w["week"], "plan": plan})
                continue
            plan_lc = raw.lower()
            chunks = [c for c in _plan_chunks(raw) if _is_significant_chunk(c)]

            found_in: int | None = None
            for j in range(i + 1, len(weeks_data)):
                for done in weeks_data[j]["work"]["completed"]:
                    done_lc = done.lower().strip()
                    if not done_lc:
                        continue
                    if plan_lc in done_lc or done_lc in plan_lc:
                        found_in = weeks_data[j]["week"]
                        break
                    if any(chunk in done_lc for chunk in chunks):
                        found_in = weeks_data[j]["week"]
                        break
                if found_in is not None:
                    break

            if found_in is not None:
                closed_plans.append(
                    {
                        "from_week": w["week"],
                        "plan": plan,
                        "completed_in": found_in,
                    }
                )
            else:
                open_plans.append({"from_week": w["week"], "plan": plan})
    return open_plans, closed_plans


def _monthly_stats(weeks: list[tuple[int, int]], weeks_data: list[dict]) -> dict[int, dict]:
    """按月统计: { month: {weeks_total, weeks_reported, work_completed, life_completed, next_week, work_notes, life_notes} }"""
    monthly: dict[int, dict] = {
        m: {
            "weeks_total": 0,
            "weeks_reported": 0,
            "work_completed": 0,
            "life_completed": 0,
            "next_week": 0,
            "work_notes": 0,
            "life_notes": 0,
        }
        for m in range(1, 13)
    }
    # 每周归属 = 「周一所在月」
    for wy, ww in weeks:
        m = week_range(wy, ww)[0].month
        if m in monthly:
            monthly[m]["weeks_total"] += 1
    for w in weeks_data:
        m = w["month"]
        monthly[m]["weeks_reported"] += 1
        monthly[m]["work_completed"] += len(w["work"]["completed"])
        monthly[m]["life_completed"] += len(w["life"]["completed"])
        monthly[m]["next_week"] += len(w["work"]["next_week"])
        monthly[m]["work_notes"] += len(w["work"]["notes"])
        monthly[m]["life_notes"] += len(w["life"]["notes"])
    return monthly


def render_yearly_markdown(
    year: int, weeks_data: list[dict], missing: list[str], monthly: dict[int, dict], totals: dict
) -> Path:
    lines: list[str] = []
    weeks_total = sum(monthly[m]["weeks_total"] for m in monthly)
    coverage_pct = (len(weeks_data) * 100 // weeks_total) if weeks_total else 0
    months_with_data = sum(1 for m in monthly if monthly[m]["weeks_reported"] > 0)

    lines.append(f"# {year} 年 · 年度汇总")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 涉及周数：**{len(weeks_data)} / {weeks_total}** 周 ({coverage_pct}% 覆盖)")
    lines.append(f"> 涉及月份：**{months_with_data} / 12** 月")
    lines.append("")

    # 月度概览
    lines.append("## 📅 月度概览")
    lines.append("")
    lines.append("| 月份 | 覆盖周数 | 工作完成 | 生活完成 | 下周计划 | 心得反思 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for m in range(1, 13):
        s = monthly[m]
        if s["weeks_reported"] > 0:
            notes_total = s["work_notes"] + s["life_notes"]
            coverage_str = f"{s['weeks_reported']}/{s['weeks_total']}"
            lines.append(
                f"| {year}-{m:02d} | {coverage_str} | {s['work_completed']} | {s['life_completed']} | {s['next_week']} | {notes_total} |"
            )
    lines.append("")

    # 排行榜
    lines.append("## 🏆 月度排行榜")
    rankable = [(m, s) for m, s in monthly.items() if s["work_completed"] > 0]
    if rankable:
        rankable.sort(key=lambda kv: kv[1]["work_completed"], reverse=True)
        for i, (m, s) in enumerate(rankable[:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            lines.append(f"- {medal} **工作最高产**：{year}-{m:02d} ({s['work_completed']} 条工作完成)")
    rankable = [(m, s) for m, s in monthly.items() if s["life_completed"] > 0]
    if rankable:
        rankable.sort(key=lambda kv: kv[1]["life_completed"], reverse=True)
        for i, (m, s) in enumerate(rankable[:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            lines.append(f"- {medal} **生活最丰富**：{year}-{m:02d} ({s['life_completed']} 条生活完成)")
    lines.append("")

    # 工作 · 全年
    def _dump_year_section(heading: str, key_path: list[str], empty_msg: str) -> None:
        lines.append(f"## {heading}")
        any_block = False
        last_m: int | None = None
        for w in weeks_data:
            items = w
            for k in key_path:
                items = items[k]
            if not items:
                continue
            any_block = True
            if w["month"] != last_m:
                lines.append(f"### 📆 {year}-{w['month']:02d}")
                last_m = w["month"]
            lines.append(f"#### {week_label(w['year'], w['week'])}")
            for it in items:
                lines.append(f"- {it}")
            lines.append("")
        if not any_block:
            lines.append(f"_(本年无{empty_msg})_")
            lines.append("")

    _dump_year_section("💼 工作 · 全年完成清单", ["work", "completed"], "工作条目")
    _dump_year_section("🌿 生活 · 全年完成清单", ["life", "completed"], "生活条目")

    # 心得合并
    lines.append("## 💡 心得 / 反思 (工作 + 生活)")
    any_block = False
    last_m = None
    for w in weeks_data:
        notes = w["work"]["notes"] + w["life"]["notes"]
        if not notes:
            continue
        any_block = True
        if w["month"] != last_m:
            lines.append(f"### 📆 {year}-{w['month']:02d}")
            last_m = w["month"]
        lines.append(f"#### {week_label(w['year'], w['week'])}")
        for it in notes:
            lines.append(f"- {it}")
        lines.append("")
    if not any_block:
        lines.append("_(本年无心得)_")
        lines.append("")

    # 下周计划追踪
    open_plans, closed_plans = _track_plans(weeks_data)
    lines.append("## 🎯 下周计划追踪")
    if closed_plans:
        lines.append(f"✅ **已完成** ({len(closed_plans)} 条 / 模糊匹配见下)")
        for p in closed_plans:
            lines.append(f"- {week_label(year, p['from_week'])} 「{p['plan']}」 → 在 W{p['completed_in']:02d} 完成")
        lines.append("")
    if open_plans:
        lines.append(f"⏳ **仍然 pending** ({len(open_plans)} 条)")
        for p in open_plans:
            lines.append(f"- {week_label(year, p['from_week'])} 「{p['plan']}」")
        lines.append("")
    if not open_plans and not closed_plans:
        lines.append("_(本年未录入过下周计划)_")
        lines.append("")

    # 总数据
    lines.append("## 📊 年度数据")
    lines.append(f"- 工作完成：**{totals['work_completed']}** 条")
    lines.append(f"- 生活完成：**{totals['life_completed']}** 条")
    lines.append(f"- 下周规划：**{totals['next_week']}** 条")
    lines.append(f"- 工作心得：**{totals['work_notes']}** 条")
    lines.append(f"- 生活心得：**{totals['life_notes']}** 条")
    lines.append(f"- 涉及周数：**{len(weeks_data)} / {weeks_total}** 周 ({coverage_pct}%)")
    lines.append(f"- 涉及月份：**{months_with_data} / 12** 月")
    lines.append("")

    out = REPORTS_DIR / str(year) / f"{year}-yearly.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def cmd_yearly(args: argparse.Namespace) -> int:
    year = args.year
    weeks = weeks_in_year(year)

    weeks_data: list[dict] = []
    missing: list[str] = []
    for wy, ww in weeks:
        work_p = report_path("work", wy, ww)
        life_p = report_path("life", wy, ww)
        work_raw = work_p.read_text(encoding="utf-8") if work_p.exists() else None
        life_raw = life_p.read_text(encoding="utf-8") if life_p.exists() else None
        if work_raw or life_raw:
            w_work = parse_section(work_raw)
            w_life = parse_section(life_raw)
            weeks_data.append(
                {
                    "year": wy,
                    "week": ww,
                    "month": week_range(wy, ww)[0].month,
                    "work": w_work,
                    "life": w_life,
                }
            )
        else:
            missing.append(week_label(wy, ww))

    if not weeks_data:
        print(f"❌ {year} 年没有任何周报，先用 `wr new` 创建一份。")
        return 1

    monthly = _monthly_stats(weeks, weeks_data)
    totals = {
        "work_completed": sum(len(w["work"]["completed"]) for w in weeks_data),
        "life_completed": sum(len(w["life"]["completed"]) for w in weeks_data),
        "next_week": sum(len(w["work"]["next_week"]) for w in weeks_data),
        "work_notes": sum(len(w["work"]["notes"]) for w in weeks_data),
        "life_notes": sum(len(w["life"]["notes"]) for w in weeks_data),
    }

    if args.format == "json":
        import json

        open_plans, closed_plans = _track_plans(weeks_data)
        payload = {
            "year": year,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "coverage": {
                "weeks_reported": len(weeks_data),
                "weeks_total": sum(monthly[m]["weeks_total"] for m in monthly),
                "missing_weeks": missing,
            },
            "monthly_breakdown": [{"month": m, **stats} for m, stats in monthly.items()],
            "totals": totals,
            "weeks": weeks_data,
            "open_plans": open_plans,
            "closed_plans": closed_plans,
        }
        out = REPORTS_DIR / str(year) / f"{year}-yearly.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ JSON 已生成：{out}")
        if missing:
            print(f"   ⚠️  缺失：{', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")
        return 0

    out = render_yearly_markdown(year, weeks_data, missing, monthly, totals)
    print(f"✅ 年度汇总已生成：{out}")
    if missing:
        print(f"   ⚠️  缺失 {len(missing)} 周：{', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")
        print(f"   补录后再跑 `wr yearly {year}` 即可重生成。")
    return 0


# ---------- 季度汇总 ----------


def weeks_in_quarter(year: int, quarter: int) -> list[tuple[int, int]]:
    """Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec. 周一落在季度内的 ISO 周。"""
    if not (1 <= quarter <= 4):
        raise ValueError("quarter 必须在 1-4 之间")
    start_month = (quarter - 1) * 3 + 1
    weeks: set[tuple[int, int]] = set()
    for m in range(start_month, start_month + 3):
        for w in weeks_starting_in_month(year, m):
            weeks.add(w)
    return sorted(weeks)


def render_quarterly_markdown(
    year: int,
    quarter: int,
    weeks_data: list[dict],
    missing: list[str],
    monthly: dict[int, dict],
    totals: dict,
    quarter_months_: tuple[int, int, int],
) -> Path:
    lines: list[str] = []
    m1, m2, m3 = quarter_months_
    weeks_total = sum(monthly[m]["weeks_total"] for m in (m1, m2, m3))
    coverage_pct = (len(weeks_data) * 100 // weeks_total) if weeks_total else 0
    months_with_data = sum(1 for m in (m1, m2, m3) if monthly[m]["weeks_reported"] > 0)

    lines.append(f"# {year} 年 Q{quarter} · 季度汇总")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 季度范围：{year}-{m1:02d} ~ {year}-{m3:02d}")
    lines.append(f"> 涉及周数：**{len(weeks_data)} / {weeks_total}** 周 ({coverage_pct}% 覆盖)")
    lines.append(f"> 涉及月份：**{months_with_data} / 3** 月")
    lines.append("")

    lines.append("## 📅 月度概览")
    lines.append("")
    lines.append("| 月份 | 覆盖周数 | 工作完成 | 生活完成 | 下周计划 | 心得反思 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for m in (m1, m2, m3):
        s = monthly[m]
        if s["weeks_reported"] > 0:
            notes_total = s["work_notes"] + s["life_notes"]
            coverage_str = f"{s['weeks_reported']}/{s['weeks_total']}"
            lines.append(
                f"| {year}-{m:02d} | {coverage_str} | {s['work_completed']} | {s['life_completed']} | {s['next_week']} | {notes_total} |"
            )
    lines.append("")

    def _dump_section(heading: str, key_path: list[str], empty_msg: str) -> None:
        lines.append(f"## {heading}")
        any_block = False
        last_m: int | None = None
        for w in weeks_data:
            items = w
            for k in key_path:
                items = items[k]
            if not items:
                continue
            any_block = True
            if w["month"] != last_m:
                lines.append(f"### 📆 {year}-{w['month']:02d}")
                last_m = w["month"]
            lines.append(f"#### {week_label(w['year'], w['week'])}")
            for it in items:
                lines.append(f"- {it}")
            lines.append("")
        if not any_block:
            lines.append(f"_(本季无{empty_msg})_")
            lines.append("")

    _dump_section("💼 工作 · 本季完成清单", ["work", "completed"], "工作条目")
    _dump_section("🌿 生活 · 本季完成清单", ["life", "completed"], "生活条目")

    lines.append("## 💡 心得 / 反思 (工作 + 生活)")
    any_block = False
    last_m = None
    for w in weeks_data:
        notes = w["work"]["notes"] + w["life"]["notes"]
        if not notes:
            continue
        any_block = True
        if w["month"] != last_m:
            lines.append(f"### 📆 {year}-{w['month']:02d}")
            last_m = w["month"]
        lines.append(f"#### {week_label(w['year'], w['week'])}")
        for it in notes:
            lines.append(f"- {it}")
        lines.append("")
    if not any_block:
        lines.append("_(本季无心得)_")
        lines.append("")

    open_plans, closed_plans = _track_plans(weeks_data)
    lines.append("## 🎯 下周计划追踪")
    if closed_plans:
        lines.append(f"✅ **已完成** ({len(closed_plans)} 条)")
        for p in closed_plans:
            lines.append(f"- {week_label(year, p['from_week'])} 「{p['plan']}」 → 在 W{p['completed_in']:02d} 完成")
        lines.append("")
    if open_plans:
        lines.append(f"⏳ **仍然 pending** ({len(open_plans)} 条)")
        for p in open_plans:
            lines.append(f"- {week_label(year, p['from_week'])} 「{p['plan']}」")
        lines.append("")
    if not open_plans and not closed_plans:
        lines.append("_(本季未录入过下周计划)_")
        lines.append("")

    lines.append("## 📊 季度数据")
    lines.append(f"- 工作完成：**{totals['work_completed']}** 条")
    lines.append(f"- 生活完成：**{totals['life_completed']}** 条")
    lines.append(f"- 下周规划：**{totals['next_week']}** 条")
    lines.append(f"- 工作心得：**{totals['work_notes']}** 条")
    lines.append(f"- 生活心得：**{totals['life_notes']}** 条")
    lines.append(f"- 涉及周数：**{len(weeks_data)} / {weeks_total}** 周 ({coverage_pct}%)")
    lines.append(f"- 涉及月份：**{months_with_data} / 3** 月")
    lines.append("")

    out = REPORTS_DIR / str(year) / f"{year}-Q{quarter}-quarterly.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def cmd_quarter(args: argparse.Namespace) -> int:
    year = args.year
    quarter = args.quarter
    if not (1 <= quarter <= 4):
        print("❌ quarter 必须在 1-4 之间")
        return 1

    quarter_months_ = ((quarter - 1) * 3 + 1, (quarter - 1) * 3 + 2, (quarter - 1) * 3 + 3)
    weeks = weeks_in_quarter(year, quarter)

    weeks_data: list[dict] = []
    missing: list[str] = []
    for wy, ww in weeks:
        work_p = report_path("work", wy, ww)
        life_p = report_path("life", wy, ww)
        work_raw = work_p.read_text(encoding="utf-8") if work_p.exists() else None
        life_raw = life_p.read_text(encoding="utf-8") if life_p.exists() else None
        if work_raw or life_raw:
            w_work = parse_section(work_raw)
            w_life = parse_section(life_raw)
            weeks_data.append(
                {
                    "year": wy,
                    "week": ww,
                    "month": week_range(wy, ww)[0].month,
                    "work": w_work,
                    "life": w_life,
                }
            )
        else:
            missing.append(week_label(wy, ww))

    if not weeks_data:
        print(f"❌ {year}-Q{quarter} 没有任何周报")
        return 1

    monthly = _monthly_stats(weeks, weeks_data)
    totals = {
        "work_completed": sum(len(w["work"]["completed"]) for w in weeks_data),
        "life_completed": sum(len(w["life"]["completed"]) for w in weeks_data),
        "next_week": sum(len(w["work"]["next_week"]) for w in weeks_data),
        "work_notes": sum(len(w["work"]["notes"]) for w in weeks_data),
        "life_notes": sum(len(w["life"]["notes"]) for w in weeks_data),
    }

    if args.format == "json":
        import json

        open_plans, closed_plans = _track_plans(weeks_data)
        payload = {
            "year": year,
            "quarter": quarter,
            "months": list(quarter_months_),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "coverage": {
                "weeks_reported": len(weeks_data),
                "weeks_total": sum(monthly[m]["weeks_total"] for m in quarter_months_),
                "missing_weeks": missing,
            },
            "monthly_breakdown": [{"month": m, **monthly[m]} for m in quarter_months_],
            "totals": totals,
            "weeks": weeks_data,
            "open_plans": open_plans,
            "closed_plans": closed_plans,
        }
        out = REPORTS_DIR / str(year) / f"{year}-Q{quarter}-quarterly.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ JSON 已生成：{out}")
        if missing:
            print(f"   ⚠️  缺失：{', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")
        return 0

    out = render_quarterly_markdown(year, quarter, weeks_data, missing, monthly, totals, quarter_months_)
    print(f"✅ 季度汇总已生成：{out}")
    if missing:
        print(f"   ⚠️  缺失 {len(missing)} 周：{', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")
        print(f"   补录后再跑 `wr quarter {year} {quarter}` 即可重生成。")
    return 0


# ---------- AI 复盘 ----------

RECAP_SYSTEM_PROMPT = "你是一位温暖而克制的个人成长教练。你直接、犀利，不灌鸡汤。用中文、第二人称「你」写作。"


def _build_recap_prompt(year: int, summary_md: str) -> str:
    """构造给 LLM 的完整提示词。"""
    return f"""# 任务

你是一位温暖而克制的「个人成长教练」。我会把 {year} 年的周报汇总 (生活 + 工作) 发给你，请基于这份材料写一份 **800-1200 字** 的年度复盘。

# 输出结构 (Markdown)

## 🌟 年度亮点 (5-7 条)
- 每条引用汇总里**具体的周次 (W##)** 与事项
- 区分「工作」和「生活」两类 (建议各占一半)
- 优先挑选「有产出」「有突破」「有持续性」的事项

## 📈 成长 / 改进建议 (3-5 条)
- 给出**可操作的下一步**，而不是空泛口号
- 每条建议要回答：如果下一年重新做这件事，你会怎么做？
- 至少包含一条「生活类」 (不只是工作)

## 🎯 明年 3 个 SMART 目标
- 每个目标都要 **Specific / Measurable / Achievable / Relevant / Time-bound**
- 至少 1 个生活类目标 (健康、家庭、兴趣都行)

---

# 风格要求

- 中文输出
- 第二人称「你」称呼用户
- 避免「加油」「努力」「坚持就是胜利」等空泛词
- 可以犀利一点 (用户已成年，不需要哄)
- 引用具体数据时直接用汇总里的数字 (条目数、周数等)

---

# 以下是 {year} 年周报汇总

{summary_md}
"""


def _ensure_yearly(year: int, refresh: bool) -> Path:
    """确保 yearly.md 存在，必要时先调用 cmd_yearly 生成。"""
    out = REPORTS_DIR / str(year) / f"{year}-yearly.md"
    if out.exists() and not refresh:
        return out
    print(f"⚙️  生成 {year} 年度汇总 (yearly.md)...")
    ns = argparse.Namespace(year=year, format="md")
    cmd_yearly(ns)
    return out


def _recap_openai(year: int, summary_md: str, args: argparse.Namespace) -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ 没有设置 OPENAI_API_KEY 环境变量。")
        print("   设置方法:  export OPENAI_API_KEY=sk-...")
        print("   或省略 --provider openai 直接打印提示词粘到 ChatGPT / Claude 也行。")
        return 1

    model = getattr(args, "model", None) or "gpt-4o-mini"
    prompt = _build_recap_prompt(year, summary_md)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": RECAP_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    print(f"🤖 调用 {model}...")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"❌ API 错误 {e.code}: {body}")
        return 1
    except urllib.error.URLError as e:
        print(f"❌ 网络错误: {e.reason}")
        print("   如果在国内, 可能需要走代理或在 gateway 处修改 base URL。")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ API 响应解析失败: {e}")
        return 1

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        print(f"❌ 响应结构异常: {e}")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
        return 1

    save = Path(args.save) if args.save else (REPORTS_DIR / str(year) / f"{year}-recap.md")
    save.parent.mkdir(parents=True, exist_ok=True)
    full = (
        f"# {year} 年 · AI 复盘\n\n"
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"> 模型：{model}\n"
        f"> 数据源：`reports/{year}/{year}-yearly.md`\n\n"
        f"---\n\n"
        f"{content}\n"
    )
    save.write_text(full, encoding="utf-8")
    print(f"\n✅ 已保存：{save}\n")
    print(content)
    return 0


def cmd_recap(args: argparse.Namespace) -> int:
    year = args.year
    yearly_path = _ensure_yearly(year, args.refresh)
    summary_md = yearly_path.read_text(encoding="utf-8")

    if args.provider == "openai":
        return _recap_openai(year, summary_md, args)

    # 默认: prompt 模式
    prompt = _build_recap_prompt(year, summary_md)
    print("📋 以下是给 LLM 的完整提示词。复制 → 粘到 ChatGPT / Claude / Gemini 都行。\n")
    print("=" * 60)
    print(prompt)
    print("=" * 60)
    print("\n💡 想自动跑出复盘? 设置 OPENAI_API_KEY 后用 `wr recap YEAR --provider openai`")
    return 0


# ---------- CLI 入口 ----------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="weekly_report",
        description="生活 / 工作 分开的周报 CLI。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="新建本周（默认）或指定周的周报")
    p_new.add_argument("--year", type=int)
    p_new.add_argument("--week", type=int)
    p_new.add_argument("--skip-life", action="store_true", help="跳过生活部分")
    p_new.add_argument("--skip-work", action="store_true", help="跳过工作部分")
    p_new.set_defaults(func=cmd_new)

    sub.add_parser("list", help="列出已有周报").set_defaults(func=cmd_list)

    p_view = sub.add_parser("view", help="查看某周的周报")
    p_view.add_argument("year", type=int)
    p_view.add_argument("week", type=int)
    p_view.set_defaults(func=cmd_view)

    p_combine = sub.add_parser("combine", help="把某周的生活+工作合并为一个文件")
    p_combine.add_argument("year", type=int)
    p_combine.add_argument("week", type=int)
    p_combine.set_defaults(func=cmd_combine)

    sub.add_parser("today", help="看看今天是第几周").set_defaults(func=cmd_today)

    p_sum = sub.add_parser("summary", help="生成月度汇总 (生活 + 工作聚合)")
    p_sum.add_argument("year", type=int)
    p_sum.add_argument("month", type=int)
    p_sum.add_argument("--format", choices=["md", "json"], default="md", help="输出格式，默认 md")
    p_sum.set_defaults(func=cmd_summary)

    p_yr = sub.add_parser("yearly", help="生成年度汇总 (按月聚合 + 下周计划追踪)")
    p_yr.add_argument("year", type=int)
    p_yr.add_argument("--format", choices=["md", "json"], default="md", help="输出格式，默认 md")
    p_yr.set_defaults(func=cmd_yearly)

    p_q = sub.add_parser("quarter", help="生成季度汇总 (Q1-Q4, 复用 _track_plans 跨周追踪)")
    p_q.add_argument("year", type=int)
    p_q.add_argument("quarter", type=int, choices=[1, 2, 3, 4], help="季度: 1=Jan-Mar, 2=Apr-Jun, 3=Jul-Sep, 4=Oct-Dec")
    p_q.add_argument("--format", choices=["md", "json"], default="md", help="输出格式，默认 md")
    p_q.set_defaults(func=cmd_quarter)

    p_recap = sub.add_parser("recap", help="生成 AI 年度复盘 (默认打印 prompt，可用 --provider openai 自动调用)")
    p_recap.add_argument("year", type=int)
    p_recap.add_argument(
        "--provider",
        choices=["prompt", "openai"],
        default="prompt",
        help="prompt (默认) = 打印提示词; openai = 调 OpenAI API",
    )
    p_recap.add_argument("--model", default="gpt-4o-mini", help="OpenAI 模型，默认 gpt-4o-mini")
    p_recap.add_argument("--save", help="(仅 openai) 保存路径，默认 reports/YEAR/YEAR-recap.md")
    p_recap.add_argument("--refresh", action="store_true", help="先重生成 yearly.md 再做复盘")
    p_recap.set_defaults(func=cmd_recap)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
