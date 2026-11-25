"""ICSLens 命令行入口。

子命令:
  audit   对 .ics 文件做健康审计，输出 JSON/CSV/Markdown/文本
  expand  展开某个重复事件在未来区间的发生时刻
  stats   输出日历负载统计
  rules   打印审计规则目录
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from typing import List

from . import __version__
from .audit import audit
from .model import Severity
from .parser import IcsParseError, parse_ics
from .report import (
    fail_exit_code,
    findings_to_csv,
    findings_to_json,
    findings_to_markdown,
    findings_to_text,
    rule_catalog_text,
)
from .rrule import RruleError, expand_rrule
from .stats import render_stats_text, stats


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="icslens",
        description="ICSLens — 零依赖 · 离线优先的 iCalendar (RFC 5545) 解析与审计引擎",
    )
    p.add_argument("--version", action="version", version=f"icslens {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("audit", help="审计 .ics 文件的规范与健康问题")
    pa.add_argument("file", help="ICS 文件路径（- 表示 stdin）")
    pa.add_argument("--format", choices=["text", "json", "csv", "md"], default="text",
                    help="输出格式（默认 text）")
    pa.add_argument("--fail-on", choices=["error", "warning", "info"], default=None,
                    help="CI 门禁：存在该级别及以上发现时以退出码 1 结束")
    pa.add_argument("--no-expansion", action="store_true",
                    help="跳过 RRULE 实际展开（更快，但失去 ICSL015 检测）")

    pe = sub.add_parser("expand", help="展开某个重复事件的发生时刻")
    pe.add_argument("file", help="ICS 文件路径")
    pe.add_argument("--uid", required=True, help="目标事件的 UID")
    pe.add_argument("--from", dest="from_str", default=None, help="起始日期 YYYY-MM-DD")
    pe.add_argument("--to", dest="to_str", default=None, help="结束日期 YYYY-MM-DD")
    pe.add_argument("--limit", type=int, default=200, help="最多输出条数（默认 200）")

    ps = sub.add_parser("stats", help="日历负载统计")
    ps.add_argument("file", help="ICS 文件路径")
    ps.add_argument("--tz", default=None, help="统计用 IANA 时区（如 Asia/Shanghai）")
    ps.add_argument("--format", choices=["text", "json"], default="text")

    sub.add_parser("rules", help="打印审计规则目录")
    return p


def _load(file: str):
    if file == "-":
        text = sys.stdin.read()
    else:
        with open(file, "r", encoding="utf-8") as fh:
            text = fh.read()
    return parse_ics(text)


def cmd_audit(args) -> int:
    try:
        cal = _load(args.file)
    except (IcsParseError, OSError) as exc:
        print(f"❌ 无法读取/解析文件: {exc}", file=sys.stderr)
        return 2
    findings = audit(cal, run_expansion=not args.no_expansion)
    if args.format == "json":
        print(findings_to_json(findings, cal))
    elif args.format == "csv":
        print(findings_to_csv(findings))
    elif args.format == "md":
        print(findings_to_markdown(findings, cal))
    else:
        print(findings_to_text(findings, cal))
    if args.fail_on:
        return fail_exit_code(findings, args.fail_on) or 0
    return 0


def cmd_expand(args) -> int:
    try:
        cal = _load(args.file)
    except (IcsParseError, OSError) as exc:
        print(f"❌ 无法读取/解析文件: {exc}", file=sys.stderr)
        return 2
    target = None
    for ev in cal.events:
        if ev.uid == args.uid:
            target = ev
            break
    if target is None:
        print(f"❌ 未找到 UID 为 {args.uid!r} 的事件", file=sys.stderr)
        return 2
    if not target.rrule:
        occurrences = [target.dtstart] if target.dtstart is not None else []
    else:
        try:
            occurrences = expand_rrule(target.dtstart, target.rrule, target.exdates,
                                       max_occurrences=max(args.limit * 4, 1000))
        except RruleError as exc:
            print(f"❌ RRULE 无法展开: {exc}", file=sys.stderr)
            return 2

    # 时间窗过滤（取本地日期分量比较，规避 aware/naive 混用异常）
    def _parse_date(s):
        try:
            y, m, d = map(int, s.split("-"))
            return date(y, m, d)
        except (ValueError, AttributeError):
            return None

    def _day_of(occ):
        if isinstance(occ, datetime):
            return occ.date()
        return occ

    lower = _parse_date(args.from_str)
    upper = _parse_date(args.to_str)

    def _in_window(occ) -> bool:
        d = _day_of(occ)
        if lower is not None and d < lower:
            return False
        if upper is not None and d > upper:
            return False
        return True

    shown = [o for o in occurrences if _in_window(o)][: args.limit]
    print(json.dumps({
        "uid": target.uid,
        "summary": target.summary,
        "occurrences": [
            o.isoformat() if hasattr(o, "isoformat") else str(o) for o in shown
        ],
        "shown": len(shown),
        "total_expanded": len(occurrences),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_stats(args) -> int:
    try:
        cal = _load(args.file)
    except (IcsParseError, OSError) as exc:
        print(f"❌ 无法读取/解析文件: {exc}", file=sys.stderr)
        return 2
    s = stats(cal, timezone_hint=args.tz)
    if args.format == "json":
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        print(render_stats_text(s))
    return 0


def main(argv: List[str] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "audit":
        return cmd_audit(args)
    if args.command == "expand":
        return cmd_expand(args)
    if args.command == "stats":
        return cmd_stats(args)
    if args.command == "rules":
        print(rule_catalog_text())
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
