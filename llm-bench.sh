#!/bin/sh
#
# LLM Benchmark - 一步启动的 CLI 压测工具（无需图形界面 / 无需安装包）。
#
# 用法（交互式向导，直接进入参数配置）：
#   curl -fsSL -o llm-bench.sh https://raw.githubusercontent.com/tatocode/lm_benchmark/main/llm-bench.sh
#   sh llm-bench.sh
#
# 也可直接传参做非交互式压测：
#   sh llm-bench.sh --base-url http://localhost:11434/v1 --model llama3 --mode step --levels 1,2,4,8
#
# 原理：把仓库源码取到缓存目录，仅安装运行所需的三个依赖（httpx / pydantic / tiktoken），
# 然后直接运行 CLI 模块——不会安装 llm-benchmark 包，也不会拉取 fastapi 等服务器依赖。
#
# 可选环境变量：
#   LMB_REPO / LMB_BRANCH   源码仓库与分支（默认 tatocode/lm_benchmark@main）
#   LMB_SRC                 直接指定本地仓库路径（跳过下载）
#   LMB_CACHE               缓存目录（默认 ~/.cache/llm-bench）
#   LMB_TARBALL             直接指定源码 tarball 地址
#   LMB_REFRESH=1           强制重新下载源码
#   LMB_PYTHON              指定 Python 版本（默认 3.12）
#
set -eu

REPO="${LMB_REPO:-https://github.com/tatocode/lm_benchmark.git}"
BRANCH="${LMB_BRANCH:-main}"
CACHE="${LMB_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/llm-bench}"
PYVER="${LMB_PYTHON:-3.12}"

REQ_HTTPX="httpx>=0.28"
REQ_PYDANTIC="pydantic>=2.13"
REQ_TIKTOKEN="tiktoken>=0.14"

die() {
    printf 'error: %s\n' "$1" >&2
    exit "${2:-1}"
}

have() {
    command -v "$1" >/dev/null 2>&1
}

# 无参数时进入交互式向导
if [ "$#" -eq 0 ]; then
    set -- --interactive
fi

looks_like_src() {
    [ -f "$1/backend/src/llm_benchmark/cli.py" ]
}

# --------------------------------------------------------------------------- #
# 1. 定位或获取源码
# --------------------------------------------------------------------------- #
SRC="${LMB_SRC:-}"
if [ -n "$SRC" ]; then
    looks_like_src "$SRC" || die "LMB_SRC 指向的目录里没有 backend/src/llm_benchmark/cli.py：$SRC"
elif looks_like_src "$PWD"; then
    SRC="$PWD"
elif [ -z "${LMB_REFRESH:-}" ] && looks_like_src "${CACHE}/src"; then
    SRC="${CACHE}/src"
else
    have curl || die "需要 curl 下载源码（或设置 LMB_SRC 指向本地仓库）"
    have tar || die "需要 tar 解压源码"
    url="${LMB_TARBALL:-}"
    if [ -z "$url" ]; then
        case "$REPO" in
            https://github.com/*)
                slug="${REPO#https://github.com/}"
                slug="${slug%.git}"
                url="https://github.com/${slug}/archive/refs/heads/${BRANCH}.tar.gz"
                ;;
            *)
                die "无法从 $REPO 推导源码地址，请用 LMB_TARBALL 指定分支压缩包"
                ;;
        esac
    fi
    printf '首次运行：正在获取源码（%s）...\n' "$url" >&2
    mkdir -p "$CACHE"
    tmp="${CACHE}/.src.$$.tar.gz"
    curl -fsSL "$url" -o "$tmp" || die "下载源码失败：$url"
    rm -rf "${CACHE}/src"
    mkdir -p "${CACHE}/src"
    tar -xzf "$tmp" -C "${CACHE}/src" --strip-components=1 || die "解压源码失败"
    rm -f "$tmp"
    SRC="${CACHE}/src"
fi

# --------------------------------------------------------------------------- #
# 2. 运行 CLI（直接跑模块，不安装 llm-benchmark 包）
# --------------------------------------------------------------------------- #
run_with_uv() {
    PYTHONPATH="${SRC}/backend/src"
    export PYTHONPATH
    exec uv run \
        --no-project --quiet --python "$PYVER" \
        --with "$REQ_HTTPX" --with "$REQ_PYDANTIC" --with "$REQ_TIKTOKEN" \
        -- python -m llm_benchmark.cli "$@"
}

find_python() {
    for c in "python${PYVER}" python3 python; do
        if have "$c" && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
            printf '%s' "$c"
            return 0
        fi
    done
    return 1
}

run_with_venv() {
    venv="${CACHE}/venv"
    if [ -x "${venv}/bin/python" ]; then
        bin="${venv}/bin/python"
    elif [ -x "${venv}/Scripts/python.exe" ]; then
        bin="${venv}/Scripts/python.exe"
    else
        py="$(find_python)" || py=""
        [ -n "$py" ] || die "未找到 uv，且本机没有 Python 3.12+。请先安装 uv：curl -LsSf https://astral.sh/uv/install.sh | sh"
        printf '首次运行：正在创建本地环境并安装运行依赖...\n' >&2
        mkdir -p "$CACHE"
        "$py" -m venv "$venv" || die "创建虚拟环境失败（可能缺少 python3-venv）"
        "${venv}/bin/pip" install --quiet --upgrade pip >/dev/null 2>&1 || true
        if [ -x "${venv}/bin/pip" ]; then
            "${venv}/bin/pip" install --quiet "$REQ_HTTPX" "$REQ_PYDANTIC" "$REQ_TIKTOKEN" || die "安装运行依赖失败"
            bin="${venv}/bin/python"
        else
            "${venv}/Scripts/pip" install --quiet "$REQ_HTTPX" "$REQ_PYDANTIC" "$REQ_TIKTOKEN" || die "安装运行依赖失败"
            bin="${venv}/Scripts/python.exe"
        fi
    fi
    export PYTHONPATH="${SRC}/backend/src"
    exec "$bin" -m llm_benchmark.cli "$@"
}

if have uv; then
    run_with_uv "$@"
else
    run_with_venv "$@"
fi
