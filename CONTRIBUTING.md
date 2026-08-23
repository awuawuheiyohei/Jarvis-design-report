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

## "Tests"

There's no formal test suite. CI runs these smoke tests on every push:

- All Python files compile (`py_compile`)
- Every subcommand renders `--help` without error
- `today` and `list` work
- `weekly_report_web` module imports cleanly
- All template functions render without error
- All `bin/*.sh` pass `bash -n`
- `com.user.weekly-report.plist` passes `plutil -lint`

Run them locally before pushing:

```bash
# Python
python3 -m py_compile weekly_report.py bin/*.py
python3 weekly_report.py --help
python3 weekly_report.py today
python3 weekly_report.py list

# Shell scripts (macOS only)
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
