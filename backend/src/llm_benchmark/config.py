import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("LMB_DATA_DIR", Path.cwd() / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'llmbench.db'}"
KEY_FILE = DATA_DIR / ".secret.key"

STATIC_DIR = Path(os.environ.get("LMB_STATIC_DIR", Path.cwd() / "static"))

IN_DOCKER = os.environ.get("LMB_IN_DOCKER", "").strip().lower() in ("1", "true", "yes")

# 容器内把出站 localhost/127.0.0.1 映射到宿主机：
# - 显式配置 LMB_MAP_LOCALHOST_HOST 时优先（可指向任意 IP/域名）；
# - 否则容器内默认 host.docker.internal（Windows/Mac Docker Desktop 原生支持；
#   Linux 需在 compose 加 extra_hosts: host.docker.internal:host-gateway）。
# 宿主机直跑（未设 LMB_IN_DOCKER）时不映射。
MAP_LOCALHOST_HOST = os.environ.get("LMB_MAP_LOCALHOST_HOST", "").strip()
if not MAP_LOCALHOST_HOST and IN_DOCKER:
    MAP_LOCALHOST_HOST = "host.docker.internal"

SNAPSHOT_INTERVAL = 0.5
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_OUTPUT_TOKENS = 256


def resolve_endpoint(endpoint: str) -> str:
    """Docker 部署时把出站请求中的 localhost/127.0.0.1 映射到宿主机地址。

    页面里继续填 localhost 即可；容器内默认映射到 host.docker.internal
    （可用 LMB_MAP_LOCALHOST_HOST 覆盖），宿主机直跑时不做映射。
    只改出站请求的目标，库内存储的原始地址保持不变。
    """
    if not MAP_LOCALHOST_HOST or not endpoint:
        return endpoint
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(endpoint)
    if parts.hostname not in ("localhost", "127.0.0.1", "::1"):
        return endpoint
    userinfo = ""
    if "@" in parts.netloc:
        userinfo = parts.netloc.rsplit("@", 1)[0] + "@"
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{userinfo}{MAP_LOCALHOST_HOST}{port}"
    return urlunsplit(
        (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
    )
