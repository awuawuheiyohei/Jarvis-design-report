#!/usr/bin/env python3
"""
weekly_report_web.py — 纯 stdlib 的 Web UI (不依赖任何第三方库)

用法:
    python3 bin/weekly_report_web.py            # 默认 127.0.0.1:8765
    python3 bin/weekly_report_web.py --port 9000
    python3 bin/weekly_report_web.py --host 0.0.0.0  # 局域网可访问

启动后浏览器打开 http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"

sys.path.insert(0, str(PROJECT_DIR))

import weekly_report as wr  # noqa: E402

# ──────────── 工具：Markdown → HTML (够用就行) ────────────


def _escape_md(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^\*]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)
    return text


def md_to_html(text: str) -> str:
    """最小 Markdown 渲染: h1-h4 / 列表 / 引用 / 表格 (|---|---|) / 段落."""
    out: list[str] = []
    lines = text.splitlines()
    in_list = False
    in_para = False
    table_buf: list[str] = []

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def flush_para():
        nonlocal in_para
        if in_para:
            out.append("</p>")
            in_para = False

    def flush_table():
        if not table_buf:
            return
        out.append('<table class="md-table">')
        for idx, row in enumerate(table_buf):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            tag = "th" if idx == 0 else "td"
            out.append("<tr>" + "".join(f"<{tag}>{_escape_md(c)}</{tag}>" for c in cells) + "</tr>")
        out.append("</table>")
        table_buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i]

        # 表格: 检测到 |---| 分隔线
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[i + 1]):
            flush_list()
            flush_para()
            flush_table()
            table_buf.append(line)
            i += 2
            while i < len(lines) and "|" in lines[i]:
                table_buf.append(lines[i])
                i += 1
            flush_table()
            continue

        if line.startswith("# "):
            flush_list()
            flush_para()
            out.append(f"<h1>{_escape_md(line[2:])}</h1>")
        elif line.startswith("## "):
            flush_list()
            flush_para()
            out.append(f"<h2>{_escape_md(line[3:])}</h2>")
        elif line.startswith("### "):
            flush_list()
            flush_para()
            out.append(f"<h3>{_escape_md(line[4:])}</h3>")
        elif line.startswith("#### "):
            flush_list()
            flush_para()
            out.append(f"<h4>{_escape_md(line[5:])}</h4>")
        elif line.startswith("> "):
            flush_list()
            flush_para()
            out.append(f"<blockquote>{_escape_md(line[2:])}</blockquote>")
        elif line.startswith("- ") or line.startswith("* "):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_escape_md(line[2:])}</li>")
        elif line.startswith("_(空)_"):
            flush_list()
            flush_para()
            out.append('<p class="empty">(无)</p>')
        elif line.strip() == "":
            flush_list()
            flush_para()
        else:
            flush_list()
            if not in_para:
                out.append("<p>")
                in_para = True
            out.append(_escape_md(line) + " ")

        i += 1

    flush_list()
    flush_para()
    flush_table()
    return "\n".join(out)


# ──────────── 工具：数据读取 ────────────


def list_all_weeks() -> list[tuple[int, int]]:
    """返回 reports/ 下所有 (year, week), 按时间倒序."""
    result: list[tuple[int, int]] = []
    if not wr.REPORTS_DIR.exists():
        return result
    for year_dir in wr.REPORTS_DIR.iterdir():
        if not year_dir.is_dir():
            continue
        try:
            y = int(year_dir.name)
        except ValueError:
            continue
        for f in year_dir.glob("[0-9]*-W[0-9][0-9]-*.md"):
            m = re.match(r"(\d+)-W(\d+)-", f.name)
            if m:
                result.append((y, int(m.group(2))))
    return sorted(set(result), key=lambda x: (x[0], x[1]), reverse=True)


def coverage_stats() -> dict:
    """当前年份的覆盖率 + 总条目数 + 连续周数 (streak)."""
    today = date.today()
    year = today.year
    streak = wr.compute_streak(today)
    json_path = wr.REPORTS_DIR / str(year) / f"{year}-yearly.json"
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            data["year"] = year
            data["streak"] = streak
            return data
        except Exception:
            pass
    return {
        "year": year,
        "streak": streak,
        "coverage": {"weeks_reported": 0, "weeks_total": 53},
        "totals": {},
    }


def week_files(year: int, week: int) -> tuple[Path | None, Path | None]:
    folder = wr.REPORTS_DIR / str(year)
    work = folder / f"{year}-W{week:02d}-work.md"
    life = folder / f"{year}-W{week:02d}-life.md"
    return (work if work.exists() else None, life if life.exists() else None)


# 编辑前自动备份: 旧文件存到 .bak/, 防误改丢数据
BAK_DIR = wr.REPORTS_DIR / ".bak"
MAX_BACKUPS_PER_FILE = 10  # 每个文件最多保留 10 个备份


def _backup_existing(path: Path | None) -> None:
    """保存前把现有文件备份到 .bak/. 每个文件最多保留 10 个.

    文件名格式: {原文件名}-{时间戳}.md.bak
    例如: 2026-W30-work-20260825-1042.md.bak
    """
    if not path or not path.exists():
        return
    import shutil as _shutil
    from datetime import datetime as _dt

    BAK_DIR.mkdir(parents=True, exist_ok=True)
    ts = _dt.now().strftime("%Y%m%d-%H%M%S")
    bak_path = BAK_DIR / f"{path.stem}-{ts}.md.bak"
    _shutil.copy2(path, bak_path)
    # 清理老的, 只留最近 MAX_BACKUPS_PER_FILE 个
    backups = sorted(BAK_DIR.glob(f"{path.stem}-*.md.bak"), reverse=True)
    for old in backups[MAX_BACKUPS_PER_FILE:]:
        old.unlink()


# ──────────── 模板 (f-string) ────────────


def tpl_base(title: str, body: str, active: str = "", port: int = 0) -> str:
    nav_items = [
        ("home", "/", "🏠 主页"),
        ("new", "/new", "✍️ 写周报"),
        ("list", "/list", "📚 历史"),
        ("yearly", f"/yearly/{date.today().year}", "📅 年度"),
    ]
    nav_html = "".join(
        '<a href="{}" {}>{}</a>'.format(
            url,
            'class="active"' if k == active else "",
            label,
        )
        for k, url, label in nav_items
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · Weekly Report</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header class="topbar">
    <div class="brand">📝 Weekly Report</div>
    <nav>{nav_html}</nav>
  </header>
  <main class="container">
    {body}
  </main>
  <footer>
    <small>running on http://127.0.0.1:{port} · 端口可通过 <code>--port</code> 修改</small>
  </footer>
</body>
</html>"""


def tpl_index(stats: dict, recent: list[tuple[int, int]]) -> str:
    today = date.today()
    y, w = wr.iso_week(today)
    mon, sun = wr.week_range(y, w)
    days_left = (sun - today).days

    cov = stats.get("coverage", {})
    reported = cov.get("weeks_reported", 0)
    total = cov.get("weeks_total", 53)
    pct = reported * 100 // total if total else 0
    totals = stats.get("totals", {})

    recent_html = (
        "".join(
            f'<li><a href="/view/{yr}/{wk}">{wr.week_label(yr, wk)}</a>'
            f' <span class="muted">({wr.week_range(yr, wk)[0]} ~ {wr.week_range(yr, wk)[1]})</span></li>'
            for yr, wk in recent[:8]
        )
        or '<li class="muted">还没有任何周报. <a href="/new">写第一份</a> 吧.</li>'
    )

    streak = stats.get("streak", 0)
    streak_fire = "🔥" if streak >= 3 else ""
    body = f"""
<section class="hero">
  <div class="hero-streak">
    <div class="num">{streak} 周</div>
    <div class="label">连续写周报 {streak_fire}</div>
  </div>
  <div class="hero-week">
    <div class="label">本周</div>
    <div class="big">{wr.week_label(y, w)}</div>
    <div class="muted">{wr.fmt_date_zh(mon)} ~ {wr.fmt_date_zh(sun)}</div>
    <div class="muted">本周还剩 <strong>{days_left}</strong> 天</div>
    <a class="btn primary" href="/new?year={y}&week={w}">✍️ 写本周周报</a>
  </div>
  <div class="hero-stats">
    <div class="stat">
      <div class="num">{reported} / {total}</div>
      <div class="label">本年已记录 ({pct}%)</div>
    </div>
    <div class="stat">
      <div class="num">{totals.get("work_completed", 0)}</div>
      <div class="label">工作完成</div>
    </div>
    <div class="stat">
      <div class="num">{totals.get("life_completed", 0)}</div>
      <div class="label">生活完成</div>
    </div>
  </div>
</section>

<section>
  <h2>最近记录</h2>
  <ul class="week-list">{recent_html}</ul>
  <p><a href="/list">查看全部 →</a></p>
</section>

<section>
  <h2>快速入口</h2>
  <div class="quick-grid">
    <a class="quick-card" href="/list"><div class="emoji">📚</div><div>所有周报<br><span class="muted" style="font-size: 0.7em">每行可编辑 / 删除</span></div></a>
    <a class="quick-card" href="/quarter/{today.year}/3"><div class="emoji">📅</div><div>Q3 季度</div></a>
    <a class="quick-card" href="/yearly/{today.year}"><div class="emoji">📊</div><div>年度汇总</div></a>
    <a class="quick-card" href="/recap/{today.year}"><div class="emoji">🤖</div><div>AI 复盘</div></a>
  </div>
</section>
"""
    return tpl_base(f"主页 ({wr.week_label(y, w)})", body, active="home", port=_PORT)


def tpl_new(
    year: int,
    week: int,
    prefill: dict | None = None,
    error: str = "",
) -> str:
    """写 / 编辑周报表单. prefill 不为 None 时是编辑模式 (从已有数据回填)."""
    mon, sun = wr.week_range(year, week)
    is_edit = prefill is not None and any(
        prefill.get(k) for k in ("work_completed", "work_next_week", "work_notes", "life_completed", "life_notes")
    )
    title_prefix = "✏️ 编辑" if is_edit else "✍️ 写"
    title_label = f"{title_prefix}周报 · {wr.week_label(year, week)}"
    save_label = "保存修改" if is_edit else "保存"

    def _val(key: str) -> str:
        """从 prefill 取值, 转成 textarea 用的多行文本."""
        if not prefill:
            return ""
        items = prefill.get(key) or []
        return "\n".join(items)

    work_p = prefill.get("work_files_exist", False) if prefill else False
    life_p = prefill.get("life_files_exist", False) if prefill else False

    body = f"""
<h1>{title_label}</h1>
<p class="muted">{wr.fmt_date_zh(mon)} (周一) ~ {wr.fmt_date_zh(sun)} (周日)</p>
{('<div class="banner-edit">✏️ 编辑模式 — 表单已从已有数据回填. 直接修改后保存即可.</div>' if is_edit else "")}

{('<div class="error">' + html.escape(error) + "</div>") if error else ""}

<form method="post" action="/new" class="report-form">
  <input type="hidden" name="year" value="{year}">
  <input type="hidden" name="week" value="{week}">

  <fieldset>
    <legend>💼 工作 {("(已记录)" if work_p else "")}</legend>
    <label>本周完成 (一行一条)</label>
    <textarea name="work_completed" rows="5" placeholder="完成了 X 项目的核心功能...">{html.escape(_val("work_completed"))}</textarea>
    <label>下周计划</label>
    <textarea name="work_next_week" rows="3" placeholder="完成 Y 模块, 准备 Z 评审...">{html.escape(_val("work_next_week"))}</textarea>
    <label>心得 / 反思</label>
    <textarea name="work_notes" rows="2" placeholder="这次踩了个坑: ...">{html.escape(_val("work_notes"))}</textarea>
  </fieldset>

  <fieldset>
    <legend>🌿 生活 {("(已记录)" if life_p else "")}</legend>
    <label>本周完成</label>
    <textarea name="life_completed" rows="4" placeholder="周末爬山, 跑了 5km...">{html.escape(_val("life_completed"))}</textarea>
    <label>心得 / 反思</label>
    <textarea name="life_notes" rows="2" placeholder="...">{html.escape(_val("life_notes"))}</textarea>
  </fieldset>

  <button type="submit" class="btn primary">{save_label}</button>
  <a href="/view/{year}/{week}" class="btn">取消</a>
</form>

<details class="hint">
  <summary>录入小提示</summary>
  <ul>
    <li>每个 textarea 里: 一行一条, 留空行不写条目</li>
    <li>觉得全部空白也行, 保存会跳过空白分类</li>
    <li><b>编辑模式</b>: 表单已自动回填已有内容, 改完直接保存</li>
    <li>想从空开始? 清空所有 textarea 再保存</li>
  </ul>
</details>
"""
    return tpl_base(f"{title_label}", body, active="new", port=_PORT)


def tpl_view(year: int, week: int, work_raw: str | None, life_raw: str | None) -> str:
    body_parts = [f"<h1>📋 {wr.week_label(year, week)}</h1>"]
    mon, sun = wr.week_range(year, week)
    body_parts.append(f'<p class="muted">{wr.fmt_date_zh(mon)} ~ {wr.fmt_date_zh(sun)}</p>')
    body_parts.append('<div class="action-bar">')
    body_parts.append(f'<a class="btn" href="/combined/{year}/{week}">合并视图</a>')
    body_parts.append(f'<a class="btn primary" href="/edit/{year}/{week}">✏️ 编辑</a>')
    body_parts.append(f'<a class="btn danger" href="/delete/{year}/{week}">🗑️ 删除</a>')
    body_parts.append("</div>")

    if work_raw:
        body_parts.append('<article class="card"><h2>💼 工作</h2>')
        body_parts.append(md_to_html(work_raw))
        body_parts.append("</article>")
    else:
        body_parts.append('<article class="card"><h2>💼 工作</h2><p class="muted">还没有记录</p></article>')

    if life_raw:
        body_parts.append('<article class="card"><h2>🌿 生活</h2>')
        body_parts.append(md_to_html(life_raw))
        body_parts.append("</article>")
    else:
        body_parts.append('<article class="card"><h2>🌿 生活</h2><p class="muted">还没有记录</p></article>')

    body = "\n".join(body_parts)
    return tpl_base(f"{wr.week_label(year, week)}", body, active="list", port=_PORT)


def tpl_combined(year: int, week: int, work_raw: str | None, life_raw: str | None) -> str:
    body_parts = [f"<h1>📋 {wr.week_label(year, week)} · 合并视图</h1>"]
    mon, sun = wr.week_range(year, week)
    body_parts.append(f'<p class="muted">{wr.fmt_date_zh(mon)} ~ {wr.fmt_date_zh(sun)}</p>')
    body_parts.append(f'<div class="action-bar"><a class="btn" href="/view/{year}/{week}">分开视图</a></div>')

    parts = []
    if work_raw:
        parts.append(work_raw)
    if life_raw:
        parts.append(life_raw)
    if parts:
        body_parts.append('<article class="card">')
        body_parts.append(md_to_html("\n\n---\n\n".join(parts)))
        body_parts.append("</article>")
    else:
        body_parts.append('<p class="muted">还没有记录.</p>')

    return tpl_base(f"{wr.week_label(year, week)} 合并", "\n".join(body_parts), active="list", port=_PORT)


def tpl_list(weeks: list[tuple[int, int]]) -> str:
    if not weeks:
        body = '<p class="muted">还没有任何周报. <a href="/new">写第一份</a></p>'
        return tpl_base("历史", body, active="list", port=_PORT)

    rows = []
    for yr, wk in weeks:
        mon, sun = wr.week_range(yr, wk)
        work_p, life_p = week_files(yr, wk)
        status_work = "✅" if work_p else "—"
        status_life = "✅" if life_p else "—"
        rows.append(
            f"<tr>"
            f'<td><a href="/view/{yr}/{wk}">{wr.week_label(yr, wk)}</a> '
            f'<a class="action-link" href="/edit/{yr}/{wk}" title="编辑">✏️</a> '
            f'<a class="action-link danger" href="/delete/{yr}/{wk}" title="删除">🗑️</a></td>'
            f'<td class="muted">{wr.fmt_date_zh(mon)} ~ {wr.fmt_date_zh(sun)}</td>'
            f'<td class="center">{status_work}</td>'
            f'<td class="center">{status_life}</td>'
            f"</tr>"
        )

    body = f"""
<h1>📚 所有周报</h1>
<p class="muted">共 {len(weeks)} 周</p>
<table class="week-table">
  <thead><tr><th>周</th><th>日期范围</th><th>工作</th><th>生活</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>
"""
    return tpl_base("历史", body, active="list", port=_PORT)


def tpl_markdown(title: str, md_text: str, nav_links: list[tuple[str, str]] | None = None) -> str:
    nav_links_html = ""
    if nav_links:
        nav_links_html = (
            '<div class="action-bar">'
            + "".join(f'<a class="btn" href="{url}">{label}</a>' for label, url in nav_links)
            + "</div>"
        )
    body = f"""
<h1>{html.escape(title)}</h1>
{nav_links_html}
<article class="card markdown-body">
{md_to_html(md_text)}
</article>
"""
    active = "yearly" if "年度" in title else ("list" if "季度" in title or "月" in title else "")
    return tpl_base(title, body, active=active, port=_PORT)


def tpl_recap(year: int, prompt: str | None = None, error: str = "") -> str:
    body = f"""
<h1>🤖 AI 复盘 · {year}</h1>
{('<div class="error">' + html.escape(error) + "</div>") if error else ""}

<p>以下是把年度汇总喂给 LLM 的完整提示词. 复制 → 粘到 ChatGPT / Claude / Gemini 都行.</p>

<details class="recap-prompt" open>
  <summary>提示词 (点击展开 / 折叠)</summary>
  <pre class="prompt-body">{html.escape(prompt) if prompt else "(需要先有 yearly.md)"}</pre>
</details>

<p>💡 想自动跑? 设置 <code>OPENAI_API_KEY</code> 环境变量后用命令行:</p>
<pre><code>export OPENAI_API_KEY=sk-...
python3 weekly_report.py recap {year} --provider openai</code></pre>

<p>结果会保存到 <code>reports/{year}/{year}-recap.md</code> 并打印到 stdout.</p>
"""
    return tpl_base(f"AI 复盘 {year}", body, active="yearly", port=_PORT)


# ──────────── HTTP handler ────────────

_PORT = 0  # set in main()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8"):
        b = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _send_file(self, path: Path, content_type: str | None = None):
        if not path.exists() or not path.is_file():
            self._send(404, "Not found", "text/plain")
            return
        ct = content_type or {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
        }.get(path.suffix.lower(), "application/octet-stream")
        self._send(200, path.read_bytes().decode("latin1"), ct)

    def _redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        try:
            path = self.path.split("?")[0]
            qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))

            if path == "/" or path == "/index.html":
                self._send(200, tpl_index(coverage_stats(), list_all_weeks()))
            elif path == "/new" or path.startswith("/edit/"):
                today = date.today()
                # /edit/YEAR/WEEK 也走同一路由
                if path.startswith("/edit/"):
                    m_edit = re.match(r"^/edit/(\d+)/(\d+)/?$", path)
                    if m_edit:
                        year = int(m_edit.group(1))
                        week = int(m_edit.group(2))
                    else:
                        self._send(404, "Bad edit URL", "text/plain")
                        return
                else:
                    year = int(qs.get("year", today.year))
                    week = int(qs.get("week", wr.iso_week(today)[1]))
                # 如果该周已有数据, 预填充
                prefill = self._build_prefill(year, week)
                self._send(200, tpl_new(year, week, prefill=prefill))
            elif path == "/list":
                self._send(200, tpl_list(list_all_weeks()))
            elif path.startswith("/static/"):
                self._send_file(STATIC_DIR / path[len("/static/") :])
            else:
                m = re.match(r"^/delete/(\d+)/(\d+)/?$", path)
                if m:
                    self._handle_delete(int(m.group(1)), int(m.group(2)))
                    return
                m = re.match(r"^/view/(\d+)/(\d+)/?$", path)
                if m:
                    year, week = int(m.group(1)), int(m.group(2))
                    work_raw = wr.read_section("work", year, week)
                    life_raw = wr.read_section("life", year, week)
                    self._send(200, tpl_view(year, week, work_raw, life_raw))
                    return
                m = re.match(r"^/combined/(\d+)/(\d+)/?$", path)
                if m:
                    year, week = int(m.group(1)), int(m.group(2))
                    work_raw = wr.read_section("work", year, week)
                    life_raw = wr.read_section("life", year, week)
                    self._send(200, tpl_combined(year, week, work_raw, life_raw))
                    return
                m = re.match(r"^/summary/(\d+)/(\d+)/?$", path)
                if m:
                    year, month = int(m.group(1)), int(m.group(2))
                    self._handle_summary(year, month)
                    return
                m = re.match(r"^/quarter/(\d+)/(\d+)/?$", path)
                if m:
                    year, q = int(m.group(1)), int(m.group(2))
                    self._handle_quarter(year, q)
                    return
                m = re.match(r"^/yearly/(\d+)/?$", path)
                if m:
                    year = int(m.group(1))
                    self._handle_yearly(year)
                    return
                m = re.match(r"^/recap/(\d+)/?$", path)
                if m:
                    year = int(m.group(1))
                    self._handle_recap(year)
                    return
                self._send(404, "Not found", "text/plain")
        except Exception:
            import traceback

            self._send(500, f"<pre>{traceback.format_exc()}</pre>")

    def do_POST(self):
        try:
            if self.path == "/new":
                self._handle_new_post()
            else:
                self._send(404, "Not found", "text/plain")
        except Exception:
            import traceback

            self._send(500, f"<pre>{traceback.format_exc()}</pre>")

    # ─── handlers ───

    def _build_prefill(self, year: int, week: int) -> dict | None:
        """读已有周报文件, 返回 dict 给表单预填充. 没数据返回 None."""
        work_path, life_path = week_files(year, week)
        prefill: dict = {
            "work_files_exist": work_path is not None,
            "life_files_exist": life_path is not None,
        }
        if not work_path and not life_path:
            return None  # 没数据, 不进入编辑模式
        if work_path:
            work_data = wr.parse_section(work_path.read_text(encoding="utf-8"))
            prefill["work_completed"] = work_data["completed"]
            prefill["work_next_week"] = work_data["next_week"]
            prefill["work_notes"] = work_data["notes"]
        if life_path:
            life_data = wr.parse_section(life_path.read_text(encoding="utf-8"))
            prefill["life_completed"] = life_data["completed"]
            prefill["life_notes"] = life_data["notes"]
        return prefill

    def _handle_new_post(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        data = dict(urllib.parse.parse_qsl(body))

        try:
            year = int(data["year"])
            week = int(data["week"])
        except (KeyError, ValueError):
            self._send(200, tpl_new(date.today().year, wr.iso_week(date.today())[1], error="year/week 不合法"))
            return

        def split_lines(s: str) -> list[str]:
            return [ln.strip() for ln in s.splitlines() if ln.strip()]

        r = wr.WeeklyReport(year=year, week=week)
        r.work.items = split_lines(data.get("work_completed", ""))
        r.work.next_week = split_lines(data.get("work_next_week", ""))
        r.work.notes = split_lines(data.get("work_notes", ""))
        r.life.items = split_lines(data.get("life_completed", ""))
        r.life.notes = split_lines(data.get("life_notes", ""))

        # 保存前备份现有文件 (防误改)
        work_path, life_path = week_files(year, week)
        _backup_existing(work_path)
        _backup_existing(life_path)

        saved = []
        if r.work.items or r.work.next_week or r.work.notes:
            saved.append(wr.write_section("work", r))
        if r.life.items or r.life.notes:
            saved.append(wr.write_section("life", r))

        if not saved:
            self._send(200, tpl_new(year, week, error="生活和工作都是空的, 没保存任何文件."))
            return
        self._redirect(f"/view/{year}/{week}")

    def _handle_delete(self, year: int, week: int) -> None:
        """删除一周的全部文件 (work + life)."""
        work_path, life_path = week_files(year, week)
        deleted = []
        for p in (work_path, life_path):
            if p and p.exists():
                p.unlink()
                deleted.append(p.name)
        if deleted:
            self._send(
                200,
                tpl_index(
                    coverage_stats(),
                    list_all_weeks(),
                ).replace(
                    "<h1>📝 Weekly Report</h1>",
                    f'<h1>🗑️ 已删除 {wr.week_label(year, week)}</h1><p class="muted">已删除: {", ".join(deleted)}</p><p><a class="btn primary" href="/">回到主页</a></p>',
                ),
            )
        else:
            self._send(404, f"{wr.week_label(year, week)} 没有文件可删", "text/plain")

    def _handle_summary(self, year: int, month: int):
        # 先确保生成最新
        try:
            wr.cmd_summary(argparse.Namespace(year=year, month=month, format="md"))
        except SystemExit:
            pass
        path = wr.REPORTS_DIR / str(year) / f"{year}-{month:02d}-summary.md"
        if not path.exists():
            self._send(404, f"{year}-{month:02d} 没有任何周报", "text/plain")
            return
        nav = [
            (f"📅 年度 {year}", f"/yearly/{year}"),
            (f"季度 {year} {(month - 1) // 3 + 1}", f"/quarter/{year}/{(month - 1) // 3 + 1}"),
            ("📚 历史", "/list"),
        ]
        self._send(200, tpl_markdown(f"{year} 年 {month} 月 · 月度汇总", path.read_text(encoding="utf-8"), nav))

    def _handle_quarter(self, year: int, q: int):
        if not (1 <= q <= 4):
            self._send(400, "quarter 必须在 1-4 之间", "text/plain")
            return
        try:
            wr.cmd_quarter(argparse.Namespace(year=year, quarter=q, format="md"))
        except SystemExit:
            pass
        path = wr.REPORTS_DIR / str(year) / f"{year}-Q{q}-quarterly.md"
        if not path.exists():
            self._send(404, f"{year}-Q{q} 没有任何周报", "text/plain")
            return
        nav = [(f"📅 年度 {year}", f"/yearly/{year}"), ("📚 历史", "/list")]
        self._send(200, tpl_markdown(f"{year} 年 Q{q} · 季度汇总", path.read_text(encoding="utf-8"), nav))

    def _handle_yearly(self, year: int):
        try:
            wr.cmd_yearly(argparse.Namespace(year=year, format="md"))
        except SystemExit:
            pass
        path = wr.REPORTS_DIR / str(year) / f"{year}-yearly.md"
        if not path.exists():
            self._send(404, f"{year} 没有任何周报", "text/plain")
            return
        nav = [("📚 历史", "/list"), (f"🤖 AI 复盘 {year}", f"/recap/{year}")]
        self._send(200, tpl_markdown(f"{year} 年 · 年度汇总", path.read_text(encoding="utf-8"), nav))

    def _handle_recap(self, year: int):
        yearly = wr.REPORTS_DIR / str(year) / f"{year}-yearly.md"
        if not yearly.exists():
            self._send(404, f"{year} 年度汇总不存在, 先访问 /yearly/{year} 生成.", "text/plain")
            return
        prompt = wr._build_recap_prompt(year, yearly.read_text(encoding="utf-8"))
        self._send(200, tpl_recap(year, prompt))


# ──────────── main ────────────


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main() -> int:
    global _PORT

    p = argparse.ArgumentParser(description="Weekly Report Web UI")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()

    if not STATIC_DIR.exists():
        print(f"❌ 找不到 static dir: {STATIC_DIR}")
        return 1

    _PORT = args.port
    server = ThreadingServer((args.host, args.port), Handler)
    print("📝 Weekly Report Web UI 已启动")
    print(f"   打开: http://{args.host}:{args.port}")
    print("   停止: Ctrl+C\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Bye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
