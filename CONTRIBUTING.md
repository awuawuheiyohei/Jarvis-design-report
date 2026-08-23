# Contributing

This is a personal tool — it's been designed for one user (me) and that shows. That said, **PRs are welcome** if you're also a weekly-report enthusiast.

## Setup

It's zero-dep — only Python 3.11+ standard library.

```bash
git clone https://github.com/awuawuheiyohei/Jarvis-design-report.git
cd Jarvis-design-report
```

## Run locally

```bash
# CLI — works anywhere
python3 weekly_report.py today

# Web UI — local browser
python3 bin/weekly_report_web.py
# → open http://127.0.0.1:8765

# Generate 5 weeks of demo data (W25-W29)
python3 bin/generate_demo.py
```

## How it works

- `reports/YEAR/` contains all data for that year
- Each week is two files: `YEAR-W##-work.md` and `YEAR-W##-life.md`
- Summary / quarterly / yearly aggregations are derived (re-runnable, idempotent)
- AI recap reads `YEAR-yearly.md` and constructs a prompt

See [README.md](README.md) for the full architecture.

## Pre-commit hooks (推荐)

装一次, 之后每次 `git commit` 会自动跑 lint / format / type check:

```bash
bash bin/install_hooks.sh
```

会跑:
- `trailing-whitespace` / `end-of-file-fixer` / `check-yaml`
- `ruff check` (auto-fix) + `ruff format`
- `mypy`

紧急跳过: `git commit --no-verify`

## Tests

CI runs **45 unit tests** + smoke tests on every push:

- **`tests/test_iso_calendar.py`** (16 tests): ISO 周数计算, 月/季度/年的周集合
- **`tests/test_file_io.py`** (10 tests): parse / write / read roundtrip, path 生成
- **`tests/test_plan_tracking.py`** (15 tests): 下周计划追踪的模糊匹配算法
- **`tests/test_cli.py`** (4 tests): 每个子命令 `--help` 能跑通

### Run locally

```bash
# 跑全部测试
python3 -m unittest discover -s tests -v

# 跑单个文件
python3 -m unittest tests.test_iso_calendar -v

# 跑单个 test case
python3 -m unittest tests.test_plan_tracking.TestPlanTracking.test_cross_week_match
```

### Smoke tests (CI 也跑)

```bash
python3 -m py_compile weekly_report.py bin/*.py
python3 weekly_report.py --help
for cmd in new list view combine today summary yearly quarter recap; do
    python3 weekly_report.py $cmd --help > /dev/null
done
python3 weekly_report.py today
python3 weekly_report.py list

for f in bin/*.sh; do bash -n "$f"; done
plutil -lint bin/com.user.weekly-report.plist
```

## Reporting issues

Open an [issue](https://github.com/awuawuheiyohei/Jarvis-design-report/issues). Include:

- What you ran (full command)
- What you expected
- What happened (paste output)
- Python version (`python3 --version`)

## Pull requests

- Keep changes focused — one feature / fix per PR
- Match existing style: PEP 8, type hints, dataclasses where used
- Update `README.md` if user-visible behavior changes
- Add an entry to `CHANGELOG.md` under `[Unreleased]`
- Smoke-test locally before pushing

## Style

- Python: `from __future__ import annotations`, `pathlib.Path`, `argparse`
- Markdown: standard CommonMark (we don't depend on a renderer)
- Shell: `bash`, `set -euo pipefail` when it makes sense
- No new dependencies without a strong reason — the tool's whole point is zero-dep

## License

By contributing, you agree your contributions are licensed under the [MIT License](LICENSE).
