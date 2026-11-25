"""日历健康审计规则集（ICSL001 ~ ICSL012）。

设计原则：每条规则独立、可解释、可关闭；ERROR 表示数据损坏或互操作性风险，
WARNING 表示常见坑，INFO 为优化建议。CI 门禁通过 --fail-on 与严重级别联动。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List

from .model import Calendar, Event, Finding, Severity
from .rrule import DEFAULT_MAX_OCCURRENCES, RruleError, expand_rrule

MAX_EXPANSION_SAFETY = DEFAULT_MAX_OCCURRENCES


def audit(cal: Calendar, run_expansion: bool = True) -> List[Finding]:
    """对已解析日历执行全部审计规则，返回按严重级别排序的发现列表。"""
    findings: List[Finding] = []
    seen_uids = {}

    for ev in cal.events:
        kind = ev.raw.get("_kind", "VEVENT")
        findings.extend(_audit_single(cal, ev, kind, seen_uids, run_expansion))

    # 文件级规则
    if not cal.prodid:
        findings.append(Finding(
            "ICSL011", Severity.WARNING,
            "缺少 PRODID：生成器信息缺失，不利于下游工具溯源诊断",
        ))
    if cal.version and cal.version != "2.0":
        findings.append(Finding(
            "ICSL012", Severity.WARNING,
            f"VERSION 为 {cal.version!r} 而非 2.0：多数现代工具仅保证 2.0 互操作",
        ))
    for w in cal.parse_warnings:
        findings.append(Finding("ICSL010", Severity.INFO, f"解析告警: {w}"))

    findings.sort(key=lambda f: (-f.severity.rank(), f.rule_id, f.uid or ""))
    return findings


def _audit_single(cal: Calendar, ev: Event, kind: str, seen_uids: dict, run_expansion: bool) -> List[Finding]:
    out: List[Finding] = []
    uid = ev.uid
    label = f"{kind} (uid={uid!r})" if uid else f"{kind} (无 UID)"

    # ICSL001 UID
    if not uid:
        out.append(Finding("ICSL001", Severity.ERROR,
                           f"{label}: 缺少 UID，同步与去重将不可用", line_no=ev.line_no))
    else:
        if uid in seen_uids:
            out.append(Finding("ICSL008", Severity.ERROR,
                               f"重复 UID {uid!r}：第 {seen_uids[uid]} 行与第 {ev.line_no} 行的两个条目将互相覆盖",
                               uid=uid, line_no=ev.line_no))
        else:
            seen_uids[uid] = ev.line_no

    # ICSL002 DTSTAMP
    if ev.dtstamp is None:
        out.append(Finding("ICSL002", Severity.WARNING,
                           f"{label}: 缺少 DTSTAMP，iTransport/同步场景要求必须存在",
                           uid=uid, line_no=ev.line_no))

    # ICSL003 DTSTART
    if ev.dtstart is None:
        out.append(Finding("ICSL003", Severity.ERROR,
                           f"{label}: 缺少 DTSTART，事件无发生时间",
                           uid=uid, line_no=ev.line_no))
        return out
    if ev.raw.get("_dtstart_error"):
        out.append(Finding("ICSL003", Severity.ERROR,
                           f"{label}: DTSTART 无法解析（{ev.raw['_dtstart_error']}）",
                           uid=uid, line_no=ev.line_no))

    # ICSL004 结束时间
    if ev.dtend is None and ev.duration is None:
        out.append(Finding("ICSL004", Severity.WARNING,
                           f"{label}: 既无 DTEND 也无 DURATION，下游只能按零时长或按规范默认处理，行为不一致",
                           uid=uid, line_no=ev.line_no))

    # ICSL005 结束早于开始
    start, end = ev.dtstart, ev.effective_end()
    if start is not None and end is not None:
        if isinstance(start, datetime) and isinstance(end, datetime):
            if end <= start:
                out.append(Finding("ICSL005", Severity.ERROR,
                                   f"{label}: 结束时间 ({end.isoformat()}) 早于等于开始时间 ({start.isoformat()})",
                                   uid=uid, line_no=ev.line_no))
        elif not isinstance(start, datetime) and not isinstance(end, datetime):
            if end < start:
                out.append(Finding("ICSL005", Severity.ERROR,
                                   f"{label}: 全天事件结束日期 ({end}) 早于开始日期 ({start})",
                                   uid=uid, line_no=ev.line_no))
        else:
            out.append(Finding("ICSL006", Severity.ERROR,
                               f"{label}: DTSTART 与 DTEND 的 VALUE 类型不一致（DATE 与 DATE-TIME 混用）",
                               uid=uid, line_no=ev.line_no))
    if ev.raw.get("_dtend_error"):
        out.append(Finding("ICSL005", Severity.ERROR,
                           f"{label}: DTEND 无法解析（{ev.raw['_dtend_error']}）",
                           uid=uid, line_no=ev.line_no))

    # ICSL007 浮动时间 + RRULE 的时区陷阱
    if isinstance(start, datetime) and start.tzinfo is None and ev.rrule:
        out.append(Finding("ICSL007", Severity.WARNING,
                           f"{label}: 带重复规则的浮动时间（无 TZID/UTC）——夏令时切换时不同实现解释不一致",
                           uid=uid, line_no=ev.line_no))

    # ICSL009 RRULE 结构与展开检查
    if ev.rrule_raw:
        if ev.rrule and ev.rrule.get("COUNT") and ev.rrule.get("UNTIL"):
            out.append(Finding("ICSL009", Severity.ERROR,
                               f"{label}: RRULE 同时包含 COUNT 与 UNTIL，规范禁止（RFC 5545 §3.3.10）",
                               uid=uid, line_no=ev.line_no))
        if run_expansion:
            out.extend(_check_expansion(cal, ev, uid, label))

    # ICSL013 空摘要
    if ev.summary is None or ev.summary.strip() == "":
        out.append(Finding("ICSL013", Severity.INFO,
                           f"{label}: SUMMARY 为空，日程列表将显示为空白条目",
                           uid=uid, line_no=ev.line_no))

    # ICSL014 未知时区
    tzid = ev.tzid
    if tzid and tzid not in cal.timezone_map:
        from . import parser as _p
        try:
            import zoneinfo as _zi
            _zi.ZoneInfo(tzid)
        except Exception:
            out.append(Finding("ICSL014", Severity.ERROR,
                               f"{label}: TZID={tzid!r} 无法被系统 IANA 时区库识别，时间将无法正确换算",
                               uid=uid, line_no=ev.line_no))
    return out


def _check_expansion(cal: Calendar, ev: Event, uid, label: str) -> List[Finding]:
    """实际展开 RRULE：捕获异常与失控规则。"""
    try:
        occ = expand_rrule(ev.dtstart, ev.rrule or {}, ev.exdates, MAX_EXPANSION_SAFETY)
    except RruleError as exc:
        return [Finding("ICSL009", Severity.ERROR,
                        f"{label}: RRULE 无法展开（{exc}）", uid=uid, line_no=ev.line_no)]
    if not ev.rrule.get("COUNT") and not ev.rrule.get("UNTIL"):
        if len(occ) >= MAX_EXPANSION_SAFETY:
            return [Finding("ICSL015", Severity.WARNING,
                            f"{label}: 无限重复规则（无 COUNT/UNTIL）且展开达到安全上限 {MAX_EXPANSION_SAFETY} 次，"
                            f"下游渲染/同步时可能失控", uid=uid, line_no=ev.line_no,
                            detail={"expanded": len(occ)})]
    return []


RULE_CATALOG = [
    ("ICSL001", "error", "缺少 UID"),
    ("ICSL002", "warning", "缺少 DTSTAMP"),
    ("ICSL003", "error", "DTSTART 缺失或非法"),
    ("ICSL004", "warning", "无 DTEND/DURATION"),
    ("ICSL005", "error", "结束早于开始 / 值非法"),
    ("ICSL006", "error", "DATE 与 DATE-TIME 混用"),
    ("ICSL007", "warning", "浮动时间 + RRULE 的时区陷阱"),
    ("ICSL008", "error", "重复 UID"),
    ("ICSL009", "error", "RRULE 结构非法或不可展开"),
    ("ICSL010", "info", "解析层告警"),
    ("ICSL011", "warning", "缺少 PRODID"),
    ("ICSL012", "warning", "VERSION 非 2.0"),
    ("ICSL013", "info", "SUMMARY 为空"),
    ("ICSL014", "error", "TZID 无法识别"),
    ("ICSL015", "warning", "无限重复规则展开失控风险"),
]
