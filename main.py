from __future__ import annotations

import argparse
from typing import Sequence

from analyzer import analyze_error
from executor import CommandResult, execute_command
from fixer import generate_fix
from log_parser import SUPPORTED_SERVICES, get_logs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Ops Agent - 轻量级服务器日志分析与安全巡检助手",
    )
    parser.add_argument(
        "-s",
        "--service",
        choices=SUPPORTED_SERVICES,
        help="日志来源：nginx、docker、system、file 或 stdin。未传时进入交互模式。",
    )
    parser.add_argument("-n", "--lines", type=int, default=80, help="采集最近多少行日志，默认 80。")
    parser.add_argument("--log-file", help="自定义日志文件路径，service=file 或 nginx 时可用。")
    parser.add_argument("--container", help="Docker 容器名或 ID，service=docker 时可用。")
    parser.add_argument("--ai", action="store_true", help="启用 AI_OPS_API_URL 指向的外部 AI 分析接口。")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行修复计划中的安全巡检命令。默认只输出建议和命令预览。",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = args.service or _prompt_service()

    print("=== AI Ops Agent ===")
    print(f"[日志来源] {service}")

    logs = get_logs(
        service,
        lines=max(args.lines, 1),
        log_file=args.log_file,
        docker_container=args.container,
    )
    print("\n[日志片段]")
    print(_clip(logs))

    analysis = analyze_error(logs, use_ai=args.ai)
    print("\n[分析结果]")
    print(analysis.as_text())

    plan = generate_fix(analysis, logs=logs)
    print("\n[修复建议]")
    print(plan.to_markdown())

    should_execute = args.execute or _prompt_execute_when_interactive(args.service)
    results = execute_command(plan.commands, dry_run=not should_execute)
    print("\n[巡检命令]")
    _print_command_results(results)

    return 0


def _prompt_service() -> str:
    options = "/".join(SUPPORTED_SERVICES)
    service = input(f"请输入要排查的日志来源 ({options}): ").strip().lower()
    if service in SUPPORTED_SERVICES:
        return service
    print(f"未识别的来源：{service}，将使用 system。")
    return "system"


def _prompt_execute_when_interactive(service_arg: str | None) -> bool:
    if service_arg is not None:
        return False
    choice = input("\n是否执行安全巡检命令？默认只预览 (y/N): ").strip().lower()
    return choice == "y"


def _print_command_results(results: list[CommandResult]) -> None:
    if not results:
        print("暂无巡检命令。")
        return

    for result in results:
        print(f"$ {result.command}")
        print(f"状态：{result.status}")
        if result.output:
            print(_clip(result.output, limit=1200))
        print()


def _clip(text: str, *, limit: int = 2000) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized or "(空)"
    return normalized[:limit] + "\n...（输出已截断）"


if __name__ == "__main__":
    raise SystemExit(main())
