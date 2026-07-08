from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass


INSPECTION_COMMANDS = {
    "cat",
    "df",
    "docker",
    "du",
    "free",
    "id",
    "ip",
    "journalctl",
    "ls",
    "lsof",
    "nginx",
    "ps",
    "ss",
    "systemctl",
}
BLOCKED_SYSTEMCTL_ACTIONS = {"restart", "stop", "start", "reload", "enable", "disable", "kill"}
BLOCKED_DOCKER_ACTIONS = {"rm", "rmi", "stop", "start", "restart", "kill", "exec", "compose"}
SHELL_OPERATORS = re.compile(r"[;&|`]|(\$\()")
PLACEHOLDER = re.compile(r"<[^>]+>|\{[^}]+\}")


@dataclass(frozen=True)
class CommandResult:
    command: str
    status: str
    output: str = ""
    returncode: int | None = None


def execute_command(command: str | list[str], *, dry_run: bool = True, timeout: int = 20) -> list[CommandResult]:
    commands = command if isinstance(command, list) else command.splitlines()
    results: list[CommandResult] = []

    for raw_command in commands:
        normalized = raw_command.strip()
        if not normalized:
            continue

        allowed, reason = is_safe_command(normalized)
        if not allowed:
            results.append(CommandResult(command=normalized, status="blocked", output=reason))
            continue

        if dry_run:
            results.append(CommandResult(command=normalized, status="dry-run", output="未执行，仅预览。"))
            continue

        results.append(_run(normalized, timeout=timeout))

    return results


def is_safe_command(command: str) -> tuple[bool, str]:
    if PLACEHOLDER.search(command):
        return False, "命令包含占位符，请人工替换并确认后再执行。"
    if SHELL_OPERATORS.search(command):
        return False, "命令包含 shell 操作符，已阻止自动执行。"

    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return False, f"命令解析失败：{exc}"

    if not parts:
        return False, "空命令。"

    executable = parts[0]
    command_parts = parts
    if executable == "sudo":
        if len(parts) < 2:
            return False, "sudo 后缺少实际命令。"
        executable = parts[1]
        command_parts = parts[1:]

    if executable not in INSPECTION_COMMANDS:
        return False, f"命令 {executable} 不在巡检命令白名单中。"

    lowered = [part.lower() for part in command_parts]
    if executable == "systemctl" and any(action in lowered for action in BLOCKED_SYSTEMCTL_ACTIONS):
        return False, "systemctl 修改类操作需要人工确认，已阻止自动执行。"
    if executable == "docker" and len(lowered) > 1 and lowered[1] in BLOCKED_DOCKER_ACTIONS:
        return False, "docker 修改类操作需要人工确认，已阻止自动执行。"
    if executable == "nginx" and "-t" not in lowered:
        return False, "仅允许自动执行 nginx -t 这类配置检查命令。"

    return True, "ok"


def _run(command: str, *, timeout: int) -> CommandResult:
    parts = shlex.split(command)
    try:
        result = subprocess.run(
            parts,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(command=command, status="error", output="命令不存在。")
    except subprocess.TimeoutExpired:
        return CommandResult(command=command, status="timeout", output=f"超过 {timeout} 秒未结束。")

    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    status = "ok" if result.returncode == 0 else "error"
    return CommandResult(command=command, status=status, output=output, returncode=result.returncode)
