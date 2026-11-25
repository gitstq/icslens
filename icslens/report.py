"""报告输出：JSON / CSV / Markdown / 终端文本 四种格式 + CI 门禁退出码。"""

from __future__ import annotations

import csv
import io
import json
import sys
from typing import List, Optional

from .model import Calendar, Finding, Severity
from .audit import RULE_CATALOG
from .stats import render_stats_text, stats

SEVERITY_ICONS = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}


def findings_to_json(findings: List[Finding], cal: Optional[Calendar] = None) -> str:
    payload = {
        "summary": {
            "total": len(findings),
            "error": sum(1 for f in findings if f.severity == Severity.ERROR),
            "warning": sum(1 for f in findings if f.severity == Severity.WARNING),
            "info": sum(1 for f in findings if f.severity == Severity.INFO),
        },
        "findings": [f.as_dict() for f in findings],
    }
    if cal is not None:
        payload["calendar"] = {
            "name": cal.calname,
            "prodid": cal.prodid,
            "version": cal.version,
            "event_count": cal.event_count,
        }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def findings_to_csv(findings: List[Finding]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["rule_id", "severity", "uid", "line_no", "message"])
    for f in findings:
        writer.writerow([f.rule_id, f.severity.value, f.uid or "", f.line_no or "", f.message])
    return buf.getvalue()


def findings_to_markdown(findings: List[Finding], cal: Optional[Calendar] = None) -> str:
    lines = ["# ICSLens 审计报告", ""]
    if cal is not None:
        lines.append(f"- 日历: **{cal.calname or '(未命名)'}**")
        lines.append(f"- 事件数: **{cal.event_count}**")
        lines.append("")
    total = len(findings)
    n_err = sum(1 for f in findings if f.severity == Severity.ERROR)
    n_warn = sum(1 for f in findings if f.severity == Severity.WARNING)
    lines.append(f"共 **{total}** 条发现：❌ {n_err} 错误 · ⚠️ {n_warn} 警告 · ℹ️ {total - n_err - n_warn} 提示")
    lines.append("")
    if findings:
        lines.append("| 级别 | 规则 | UID | 行号 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for f in findings:
            lines.append(
                f"| {SEVERITY_ICONS[f.severity.value]} {f.severity.value} | {f.rule_id} "
                f"| {f.uid or '-'} | {f.line_no or '-'} | {f.message} |"
            )
    else:
        lines.append("✅ 未发现任何问题。")
    return "\n".join(lines)


def findings_to_text(findings: List[Finding], cal: Optional[Calendar] = None) -> str:
    lines = ["🔬 ICSLens 审计报告", ""]
    if cal is not None:
        lines.append(f"📅 日历: {cal.calname or '(未命名)'} · 事件 {cal.event_count} 个")
    n_err = sum(1 for f in findings if f.severity == Severity.ERROR)
    n_warn = sum(1 for f in findings if f.severity == Severity.WARNING)
    lines.append(f"共 {len(findings)} 条：❌ {n_err} · ⚠️ {n_warn} · ℹ️ {len(findings) - n_err - n_warn}")
    lines.append("-" * 60)
    for f in findings:
        icon = SEVERITY_ICONS[f.severity.value]
        loc = f" L{f.line_no}" if f.line_no else ""
        lines.append(f"{icon} [{f.rule_id}{loc}] {f.message}")
    if not findings:
        lines.append("✅ 未发现任何问题。")
    return "\n".join(lines)


def fail_exit_code(findings: List[Finding], fail_on: str) -> Optional[int]:
    """CI 门禁：若存在 >= fail_on 级别的发现，返回退出码 1，否则 None。"""
    threshold = Severity(fail_on)
    for f in findings:
        if f.severity.rank() >= threshold.rank():
            return 1
    return None


def rule_catalog_text() -> str:
    lines = ["规则编号 | 级别 | 含义", "--- | --- | ---"]
    for rid, sev, desc in RULE_CATALOG:
        lines.append(f"{rid} | {sev} | {desc}")
    return "\n".join(lines)
