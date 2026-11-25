"""ICSLens 数据模型：Calendar / Event / Finding。全部为纯标准库实现。"""

from __future__ import annotations

import zoneinfo
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """审计发现严重级别，与 CI 门禁配合使用。"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def rank(self) -> int:
        return {"info": 0, "warning": 1, "error": 2}[self.value]


@dataclass
class Finding:
    """一条审计发现。

    Attributes:
        rule_id: 规则编号，例如 ``ICSL001``。
        severity: 严重级别。
        message: 人类可读的说明。
        uid: 关联事件的 UID（全局性问题时为 None）。
        line_no: 关联源文件行号（若可定位）。
        detail: 附加结构化信息。
    """

    rule_id: str
    severity: Severity
    message: str
    uid: Optional[str] = None
    line_no: Optional[int] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "uid": self.uid,
            "line_no": self.line_no,
            "detail": self.detail,
        }


@dataclass
class Event:
    """一个 VEVENT（或简化 VTODO）条目。

    dtstart/dtend 为 aware datetime（UTC 或 zoneinfo）或 date（全天事件）。
    解析阶段尽量容错：无法解析的字段保留原始字符串到 ``raw``。
    """

    uid: Optional[str] = None
    summary: Optional[str] = None
    dtstart: Optional[Any] = None  # datetime | date | None
    dtend: Optional[Any] = None
    duration: Optional[timedelta] = None
    all_day: bool = False
    tzid: Optional[str] = None
    rrule: Optional[Dict[str, str]] = None
    rrule_raw: Optional[str] = None
    exdates: List[Any] = field(default_factory=list)
    rdates: List[Any] = field(default_factory=list)
    location: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    dtstamp: Optional[datetime] = None
    has_valarm: bool = False
    line_no: Optional[int] = None
    raw: Dict[str, str] = field(default_factory=dict)

    def effective_end(self) -> Optional[Any]:
        """DTEND / DURATION 归一化后的结束时间。"""
        if self.dtend is not None:
            return self.dtend
        if self.duration is not None and self.dtstart is not None:
            if isinstance(self.dtstart, datetime):
                return self.dtstart + self.duration
            return self.dtstart + self.duration  # date + timedelta -> date
        return None

    def duration_minutes(self) -> Optional[float]:
        end = self.effective_end()
        if self.dtstart is None or end is None:
            return None
        start = self.dtstart
        if isinstance(start, datetime) and isinstance(end, datetime):
            return (end - start).total_seconds() / 60.0
        if not isinstance(start, datetime) and not isinstance(end, datetime):
            return (end - start).days * 24 * 60.0
        return None


@dataclass
class Calendar:
    """一个已解析的 iCalendar 文件。"""

    prodid: Optional[str] = None
    version: Optional[str] = None
    calname: Optional[str] = None
    events: List[Event] = field(default_factory=list)
    parse_warnings: List[str] = field(default_factory=list)
    timezone_map: Dict[str, zoneinfo.ZoneInfo] = field(default_factory=dict)

    @property
    def event_count(self) -> int:
        return len(self.events)
