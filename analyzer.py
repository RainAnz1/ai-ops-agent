from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Iterable

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency path
    requests = None


@dataclass(frozen=True)
class AnalysisResult:
    issue_type: str
    severity: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "rules"

    def as_text(self) -> str:
        evidence = "\n".join(f"- {line}" for line in self.evidence) or "- 暂无关键日志片段"
        return (
            f"错误类型：{self.issue_type}\n"
            f"严重级别：{self.severity}\n"
            f"置信度：{self.confidence:.0%}\n"
            f"来源：{self.source}\n"
            f"摘要：{self.summary}\n"
            f"证据：\n{evidence}"
        )


@dataclass(frozen=True)
class ErrorRule:
    issue_type: str
    severity: str
    summary: str
    patterns: tuple[str, ...]


RULES: tuple[ErrorRule, ...] = (
    ErrorRule(
        issue_type="端口占用",
        severity="high",
        summary="服务尝试监听的端口已经被其他进程占用。",
        patterns=(
            r"address already in use",
            r"bind\(\).*failed",
            r"eaddrinuse",
            r"port is already allocated",
            r"listen tcp .*bind",
        ),
    ),
    ErrorRule(
        issue_type="权限问题",
        severity="high",
        summary="进程缺少读取、写入或绑定资源所需的权限。",
        patterns=(
            r"permission denied",
            r"operation not permitted",
            r"eacces",
            r"\(13: permission denied\)",
        ),
    ),
    ErrorRule(
        issue_type="磁盘空间不足",
        severity="critical",
        summary="磁盘空间或 inode 耗尽，可能导致写日志、创建文件或启动服务失败。",
        patterns=(
            r"no space left on device",
            r"disk full",
            r"enospc",
            r"not enough space",
        ),
    ),
    ErrorRule(
        issue_type="内存不足",
        severity="critical",
        summary="系统或容器发生 OOM，进程可能被内核终止。",
        patterns=(
            r"out of memory",
            r"oom-killer",
            r"killed process",
            r"cannot allocate memory",
            r"memory limit",
        ),
    ),
    ErrorRule(
        issue_type="配置语法错误",
        severity="high",
        summary="配置文件存在语法、字段或指令错误，服务无法加载配置。",
        patterns=(
            r"unknown directive",
            r"invalid number of arguments",
            r"configuration file .* test failed",
            r"yaml: line \d+",
            r"did not find expected",
            r"syntax error",
        ),
    ),
    ErrorRule(
        issue_type="网络连接异常",
        severity="medium",
        summary="服务访问上游、DNS 或本机网络资源时出现连接异常。",
        patterns=(
            r"connection refused",
            r"connection timed out",
            r"temporary failure in name resolution",
            r"name or service not known",
            r"no route to host",
            r"upstream timed out",
        ),
    ),
    ErrorRule(
        issue_type="服务启动失败",
        severity="high",
        summary="服务进程启动或保活失败，需要结合 systemd、容器状态和应用日志继续定位。",
        patterns=(
            r"failed to start",
            r"main process exited",
            r"start request repeated too quickly",
            r"failed with result",
            r"exited with code",
            r"crashloopbackoff",
            r"unhealthy",
        ),
    ),
)


def analyze_error(logs: str, use_ai: bool = False) -> AnalysisResult:
    cleaned_logs = logs.strip()
    if not cleaned_logs:
        return AnalysisResult(
            issue_type="无日志内容",
            severity="low",
            summary="没有采集到可分析的日志内容。",
            confidence=1.0,
        )

    if use_ai:
        ai_result = _try_ai_analysis(cleaned_logs)
        if ai_result is not None:
            return ai_result

    return _rule_based_analysis(cleaned_logs)


def _rule_based_analysis(logs: str) -> AnalysisResult:
    scored: list[tuple[int, ErrorRule, list[str]]] = []
    lower_logs = logs.lower()

    for rule in RULES:
        evidence = _collect_evidence(logs, rule.patterns)
        score = sum(1 for pattern in rule.patterns if re.search(pattern, lower_logs, re.IGNORECASE))
        if evidence or score:
            scored.append((score + len(evidence), rule, evidence))

    if not scored:
        return AnalysisResult(
            issue_type="未知错误",
            severity="medium",
            summary="暂未匹配到内置规则，建议结合完整日志、服务状态和最近变更继续排查。",
            evidence=_first_non_empty_lines(logs, limit=3),
            confidence=0.35,
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    score, rule, evidence = scored[0]
    confidence = min(0.95, 0.55 + score * 0.1)
    return AnalysisResult(
        issue_type=rule.issue_type,
        severity=rule.severity,
        summary=rule.summary,
        evidence=evidence[:5],
        confidence=confidence,
    )


def _try_ai_analysis(logs: str) -> AnalysisResult | None:
    endpoint = os.getenv("AI_OPS_API_URL")
    if not endpoint or requests is None:
        return None

    prompt = (
        "请分析以下服务器日志，输出 JSON，字段包含 issue_type、severity、summary、evidence、confidence。"
        "severity 可选 low/medium/high/critical。\n\n"
        f"{logs}"
    )
    try:
        response = requests.post(
            endpoint,
            json={"prompt": prompt, "logs": logs},
            timeout=float(os.getenv("AI_OPS_API_TIMEOUT", "15")),
        )
        response.raise_for_status()
    except Exception:
        return None

    return _parse_ai_response(response.text)


def _parse_ai_response(text: str) -> AnalysisResult | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return AnalysisResult(
            issue_type="AI 分析结果",
            severity="medium",
            summary=text.strip()[:500] or "AI 接口返回空内容。",
            confidence=0.6,
            source="ai",
        )

    return AnalysisResult(
        issue_type=str(payload.get("issue_type") or payload.get("type") or "未知错误"),
        severity=str(payload.get("severity") or "medium"),
        summary=str(payload.get("summary") or payload.get("message") or "AI 未返回摘要。"),
        evidence=_normalize_evidence(payload.get("evidence")),
        confidence=float(payload.get("confidence") or 0.75),
        source="ai",
    )


def _collect_evidence(logs: str, patterns: Iterable[str]) -> list[str]:
    evidence: list[str] = []
    for line in logs.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns):
            evidence.append(normalized)
    return evidence


def _first_non_empty_lines(logs: str, limit: int) -> list[str]:
    lines = [line.strip() for line in logs.splitlines() if line.strip()]
    return lines[:limit]


def _normalize_evidence(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
