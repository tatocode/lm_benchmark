#!/bin/sh
#
# LLM Benchmark - 一行命令启动的 CLI 压测工具（无需图形界面）。
#
# 用法（交互式向导）：
#   curl -fsSL -o llm-bench.sh https://raw.githubusercontent.com/tatocode/lm_benchmark/main/llm-bench.sh
#   sh llm-bench.sh
#
# 也可直接传参做非交互式压测：
#   sh llm-bench.sh --base-url http://localhost:11434/v1 --model llama3 --mode step --levels 1,2,4,8
#
# 注意：请先下载再运行（不要用 `curl ... | sh`），否则交互输入无法读取终端。
# 依赖：Python 3.12+（若已装 uv/uvx 会自动准备运行时）。
# 脚本优先用 uv/uvx，其次 pipx，最后回退到临时 venv 安装。
#
set -eu

# 包在仓库的 backend/ 子目录中（PEP 508 `#subdirectory=` 片段）。
REPO="${LMB_REPO:-https://github.com/tatocode/lm_benchmark.git}"
PKG_SPEC="git+${REPO}#subdirectory=backend"

# 避免在用户目录生成无用的 data 目录（CLI 不使用数据库）
DATA_DIR="${LMB_DATA_DIR:-${TMPDIR:-/tmp}/llm-bench-data}"

die() {
    printf 'error: %s\n' "$1" >&2
    exit "${2:-1}"
}

have() {
    command -v "$1" >/dev/null 2>&1
}

find_python() {
    for c in python3 python; do
        if have "$c" && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
            printf '%s' "$c"
            return 0
        fi
    done
    return 1
}

# 无参数时进入交互式向导
if [ "$#" -eq 0 ]; then
    set -- --interactive
fi

# 优先使用 uv/uvx：它们会自动准备 Python 3.12+ 运行时，无需本机预装对应版本
if have uvx; then
    exec env LMB_DATA_DIR="$DATA_DIR" uvx --from "$PKG_SPEC" llm-bench "$@"
fi

if have uv; then
    exec env LMB_DATA_DIR="$DATA_DIR" uv tool run --from "$PKG_SPEC" llm-bench "$@"
fi

# 以下回退方式依赖本机已安装的 Python 3.12+
PY="$(find_python)" || PY=""
if [ -z "$PY" ]; then
    cat >&2 <<'EOF'
error: 未找到 Python 3.12+（且未安装 uv/uvx）。

推荐安装 uv（会自动准备 Python 运行时）：
  curl -LsSf https://astral.sh/uv/install.sh | sh

或直接安装 Python 3.12+：
  Debian/Ubuntu : sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
  Fedora/RHEL   : sudo dnf install -y python3 python3-pip
  macOS         : brew install python@3.12
  Windows       : winget install Python.Python.3.12  或访问 https://www.python.org/downloads/
EOF
    die "安装 Python 3.12+ 或 uv 后重试"
fi

if have pipx; then
    exec env LMB_DATA_DIR="$DATA_DIR" pipx run --spec "$PKG_SPEC" llm-bench "$@"
fi

# 回退：临时 venv
VENV="${TMPDIR:-/tmp}/llm-bench-venv"
BIN="$VENV/bin/llm-bench"
[ -x "$BIN" ] || BIN="$VENV/Scripts/llm-bench"   # Windows / Git Bash

if [ ! -x "$BIN" ]; then
    printf '首次运行：正在创建虚拟环境并安装依赖（%s）...\n' "$VENV" >&2
    "$PY" -m venv "$VENV" || die "创建虚拟环境失败（可能缺少 python3-venv）"
    "$VENV/bin/pip" install --quiet --upgrade pip >/dev/null 2>&1 || true
    if [ -x "$VENV/bin/pip" ]; then
        "$VENV/bin/pip" install --quiet "$PKG_SPEC" || die "安装依赖失败"
        BIN="$VENV/bin/llm-bench"
    else
        "$VENV/Scripts/pip" install --quiet "$PKG_SPEC" || die "安装依赖失败"
        BIN="$VENV/Scripts/llm-bench"
    fi
fi

exec env LMB_DATA_DIR="$DATA_DIR" "$BIN" "$@"
