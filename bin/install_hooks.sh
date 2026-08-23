#!/usr/bin/env bash
# install_hooks.sh - 一键装 pre-commit hooks
# 跑一次, 以后 commit 自动跑 ruff + mypy + 文件检查

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "📦 装 pre-commit (dev 依赖)..."
if ! command -v pre-commit >/dev/null 2>&1; then
    pip3 install --user --break-system-packages pre-commit 2>&1 | tail -3
    export PATH="$HOME/Library/Python/3.14/bin:$PATH"
fi

echo "🔧 git init hooks..."
if [ ! -d .git ]; then
    echo "❌ 不是 git 仓库"
    exit 1
fi

pre-commit install

echo ""
echo "✅ 完成. 以后每次 git commit 都会自动跑:"
echo "   - trailing-whitespace + end-of-file-fixer"
echo "   - ruff check + ruff format"
echo "   - mypy"
echo ""
echo "手动跑全部: pre-commit run --all-files"
echo "跳过 hook (紧急): git commit --no-verify"
