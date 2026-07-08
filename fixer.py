from __future__ import annotations

import re
from dataclasses import dataclass, field

from analyzer import AnalysisResult


@dataclass(frozen=True)
class FixPlan:
    issue_type: str
    title: str
    explanation: str
    commands: list[str] = field(default_factory=list)
    manual_steps: list[str] = field(default_factory=list)
    risk: str = "low"

    def to_markdown(self) -> str:
        commands = "\n".join(f"- `{command}`" for command in self.commands) or "- 暂无可安全自动执行的巡检命令"
        steps = "\n".join(f"- {step}" for step in self.manual_steps) or "- 暂无额外人工步骤"
        return (
            f"### {self.title}\n"
            f"{self.explanation}\n\n"
            f"风险级别：{self.risk}\n\n"
            f"建议先执行的巡检命令：\n{commands}\n\n"
            f"人工确认后再处理：\n{steps}"
        )


def generate_fix(analysis: AnalysisResult | str, logs: str = "") -> FixPlan:
    issue_type = analysis.issue_type if isinstance(analysis, AnalysisResult) else analysis
    port = _extract_port(logs)

    plans = {
        "端口占用": _port_in_use_plan(port),
        "权限问题": FixPlan(
            issue_type="权限问题",
            title="检查文件、目录或端口权限",
            explanation="先确认报错资源的属主和权限，再决定是否调整用户、组或 systemd 配置。",
            commands=["id", "ps aux", "ls -la"],
            manual_steps=[
                "定位日志里出现的具体文件、目录或端口。",
                "确认服务运行用户是否应该拥有该资源的读取或写入权限。",
                "只对明确的目标路径执行 chmod/chown，避免递归修改系统目录。",
            ],
            risk="medium",
        ),
        "磁盘空间不足": FixPlan(
            issue_type="磁盘空间不足",
            title="释放磁盘空间或扩容",
            explanation="磁盘或 inode 耗尽会让服务无法写日志、缓存或临时文件。",
            commands=["df -h", "df -ih", "du -xh /var/log"],
            manual_steps=[
                "清理明确可删除的旧日志、缓存或构建产物。",
                "检查日志轮转策略，避免日志继续无限增长。",
                "如果业务数据持续增长，优先扩容而不是反复手动清理。",
            ],
            risk="high",
        ),
        "内存不足": FixPlan(
            issue_type="内存不足",
            title="定位 OOM 进程和内存压力来源",
            explanation="OOM 通常需要同时检查系统内存、容器限制和最近部署变更。",
            commands=["free -h", "ps aux", "journalctl -k --no-pager -n 80"],
            manual_steps=[
                "找出被 OOM killer 终止的进程和时间点。",
                "检查容器或 systemd 的内存限制是否过低。",
                "结合流量、任务队列和最近发布判断是否存在内存泄漏。",
            ],
            risk="high",
        ),
        "配置语法错误": FixPlan(
            issue_type="配置语法错误",
            title="校验配置并回滚错误变更",
            explanation="配置错误应先用服务自带的检查命令验证，再重载或重启。",
            commands=["nginx -t", "systemctl status nginx --no-pager"],
            manual_steps=[
                "根据报错行号打开对应配置文件。",
                "修正语法后重新运行配置检查命令。",
                "确认检查通过后再执行 reload 或 restart。",
            ],
            risk="medium",
        ),
        "网络连接异常": FixPlan(
            issue_type="网络连接异常",
            title="检查上游连通性和 DNS",
            explanation="网络类问题需要确认本机端口、上游地址、DNS 和防火墙策略。",
            commands=["ss -lntp", "ip route", "cat /etc/resolv.conf"],
            manual_steps=[
                "从日志里提取失败的域名、IP 和端口。",
                "在服务器本机验证 DNS 解析和 TCP 连接。",
                "检查安全组、防火墙、反向代理 upstream 配置和上游服务状态。",
            ],
            risk="medium",
        ),
        "服务启动失败": FixPlan(
            issue_type="服务启动失败",
            title="查看服务状态和最近启动日志",
            explanation="先读取 systemd 或容器的启动失败原因，再决定重启、回滚或修配置。",
            commands=["systemctl status nginx --no-pager", "journalctl -u nginx --no-pager -n 80", "docker ps -a --no-trunc"],
            manual_steps=[
                "确认失败服务名称，不要直接套用 nginx 示例命令。",
                "如果是刚发布后失败，优先对比配置、环境变量和依赖版本。",
                "修复根因后再重启服务，并观察 5 到 10 分钟。",
            ],
            risk="medium",
        ),
        "无日志内容": FixPlan(
            issue_type="无日志内容",
            title="补充日志来源",
            explanation="当前没有足够信息进行判断。",
            commands=[],
            manual_steps=[
                "确认服务名、日志文件路径或容器名是否正确。",
                "使用 --log-file 或 --container 提供更明确的日志来源。",
            ],
            risk="low",
        ),
    }

    return plans.get(
        issue_type,
        FixPlan(
            issue_type=issue_type,
            title="继续人工排查",
            explanation="内置规则暂未覆盖该问题，建议从日志上下文、服务状态和最近变更入手。",
            commands=["systemctl --failed --no-pager", "journalctl -xe --no-pager -n 80", "docker ps -a --no-trunc"],
            manual_steps=[
                "补充更完整的错误日志和服务启动日志。",
                "确认问题首次出现时间点，并回看当时的发布、配置或机器变更。",
                "把明确的新错误模式补充到 analyzer.py 的规则中。",
            ],
            risk="medium",
        ),
    )


def _port_in_use_plan(port: str | None) -> FixPlan:
    target = f" :{port}" if port else ""
    commands = ["ss -lntp", "sudo lsof -iTCP -sTCP:LISTEN -P -n"]
    if port:
        commands.insert(0, f"sudo lsof -i :{port}")

    return FixPlan(
        issue_type="端口占用",
        title="定位占用端口的进程",
        explanation=f"先找出正在监听{target} 的进程，再判断是停止冲突进程还是修改服务监听端口。",
        commands=commands,
        manual_steps=[
            "确认占用端口的进程是否属于预期服务。",
            "如果是旧进程残留，优雅停止它；如果是正常服务，调整新服务端口。",
            "变更后重新启动目标服务，并再次确认监听状态。",
        ],
        risk="medium",
    )


def _extract_port(logs: str) -> str | None:
    patterns = (
        r"0\.0\.0\.0:(\d+)",
        r"127\.0\.0\.1:(\d+)",
        r"\[::\]:(\d+)",
        r":(\d+)\s+failed",
        r"port\s+(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, logs, re.IGNORECASE)
        if match:
            return match.group(1)
    return None
