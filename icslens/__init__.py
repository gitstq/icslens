"""ICSLens — 零依赖 · 离线优先的 iCalendar (RFC 5545) 解析与审计引擎。

模块结构:
- model    : 数据模型 (Calendar / Event / Finding)
- parser   : RFC 5545 行展开与组件解析
- rrule    : RRULE 重复规则展开引擎
- audit    : 日历健康审计规则集
- report   : JSON / CSV / Markdown / 文本 报告输出
- stats    : 日历负载统计分析
- cli      : 命令行入口
"""

__version__ = "1.0.0"

from .model import Calendar, Event, Finding, Severity
from .parser import parse_ics, IcsParseError

__all__ = [
    "Calendar",
    "Event",
    "Finding",
    "Severity",
    "parse_ics",
    "IcsParseError",
    "__version__",
]
