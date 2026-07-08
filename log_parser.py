from __future__ import annotations

import subprocess
import sys
from collections import deque
from pathlib import Path


SUPPORTED_SERVICES = ("nginx", "docker", "system", "file", "stdin")
DEFAULT_NGINX_LOGS = (
    Path("/var/log/nginx/error.log"),
    Path("/usr/local/var/log/nginx/error.log"),
    Path("/opt/homebrew/var/log/nginx/error.log"),
)


def get_logs(
    service: str,
    *,
    lines: int = 80,
    log_file: str | None = None,
    docker_container: str | None = None,
) -> str:
    service = service.strip().lower()
    if service == "nginx":
        return _get_nginx_logs(lines=lines, log_file=log_file)
    if service == "docker":
        return _get_docker_logs(lines=lines, container=docker_container)
    if service == "system":
        return _run_command(["journalctl", "-xe", "--no-pager", "-n", str(lines)])
    if service == "file":
        if not log_file:
            return "读取失败：使用 file 来源时必须传入 --log-file。"
        return _tail_file(Path(log_file), lines)
    if service == "stdin":
        return sys.stdin.read()

    return f"未知服务：{service}。支持的服务：{', '.join(SUPPORTED_SERVICES)}"


def _get_nginx_logs(*, lines: int, log_file: str | None) -> str:
    if log_file:
        return _tail_file(Path(log_file), lines)

    for path in DEFAULT_NGINX_LOGS:
        if path.exists():
            return _tail_file(path, lines)

    return (
        "未找到 Nginx 错误日志。可使用 --log-file 指定路径，常见路径包括："
        + ", ".join(str(path) for path in DEFAULT_NGINX_LOGS)
    )


def _get_docker_logs(*, lines: int, container: str | None) -> str:
    if container:
        return _run_command(["docker", "logs", "--tail", str(lines), container])
    return _run_command(["docker", "ps", "-a", "--no-trunc"])


def _tail_file(path: Path, lines: int) -> str:
    if not path.exists():
        return f"读取失败：文件不存在：{path}"
    if not path.is_file():
        return f"读取失败：不是普通文件：{path}"

    try:
        with path.open("r", encoding="utf-8", errors="replace") as file:
            return "".join(deque(file, maxlen=lines))
    except OSError as exc:
        return f"读取失败：{exc}"


def _run_command(args: list[str], timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return f"命令不存在：{args[0]}，请确认本机已安装并在 PATH 中。"
    except subprocess.TimeoutExpired:
        return f"命令超时：{' '.join(args)}"

    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    if result.returncode == 0:
        return output or "命令执行成功，但没有输出。"

    return "\n".join(part for part in (output, error) if part) or f"命令失败，退出码：{result.returncode}"
