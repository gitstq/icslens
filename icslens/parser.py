"""RFC 5545 解析器：行展开（folding）、内容行切分、VEVENT 组件解析。

零依赖实现，容错优先：单条坏数据不阻断整体解析，问题进入
``Calendar.parse_warnings`` 或作为审计发现呈现。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .model import Calendar, Event

try:  # Python 3.9+ 标准库，非第三方依赖
    import zoneinfo
except ImportError:  # pragma: no cover
    zoneinfo = None  # type: ignore


class IcsParseError(Exception):
    """文件级不可恢复错误（例如不存在 VCALENDAR 包装）。"""


def unfold_lines(text: str) -> List[Tuple[int, str]]:
    """执行 RFC 5545 §3.1 行展开：CRLF + 空格/制表符开头的行为续行。

    Returns:
        (原始行号, 展开后内容) 列表；行号从 1 开始，指向续行首行。
    """
    result: List[Tuple[int, str]] = []
    raw_lines = text.splitlines()
    i = 0
    line_no = 0
    while i < len(raw_lines):
        line_no += 1
        current = raw_lines[i]
        i += 1
        if current == "":
            continue
        # 去掉 UTF-8 BOM 与多余 CR
        current = current.lstrip("\ufeff").rstrip("\r")
        while i < len(raw_lines) and raw_lines[i] != "" and raw_lines[i][:1] in (" ", "\t"):
            current += raw_lines[i][1:].rstrip("\r")
            i += 1
        result.append((line_no, current))
    return result


def split_content_line(line: str) -> Optional[Tuple[str, List[Tuple[str, str]], str]]:
    """按 RFC 5545 §3.1 切分内容行为 (NAME, params, value)。

    引号内的分号/冒号不参与切分。
    """
    name_end = -1
    params: List[Tuple[str, str]] = []
    in_quote = False
    colon_pos = -1
    semi_pos = -1
    for idx, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif in_quote:
            continue
        elif ch == ":" and colon_pos == -1:
            colon_pos = idx
            break
        elif ch == ";" and semi_pos == -1 and colon_pos == -1:
            semi_pos = idx
    if colon_pos == -1:
        return None
    if semi_pos != -1:
        name_end = semi_pos
    else:
        name_end = colon_pos
    name = line[:name_end].upper()
    param_part = line[name_end:colon_pos]
    value = line[colon_pos + 1 :]
    if param_part:
        for chunk in _split_respect_quotes(param_part[1:], ";"):
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                params.append((k.upper(), v.strip('"')))
    return name, params, value


def _split_respect_quotes(text: str, sep: str) -> List[str]:
    out: List[str] = []
    buf = []
    in_quote = False
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
            buf.append(ch)
        elif ch == sep and not in_quote:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [s for s in out if s != ""]


def unescape_text(value: str) -> str:
    """反转义 TEXT 值中的 \\n \\, \\; \\\\。"""
    out = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt in ("n", "N"):
                out.append("\n")
                i += 2
                continue
            if nxt in (",", ";", "\\", '"'):
                out.append(nxt)
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_ics_datetime(value: str, params: Dict[str, str], tzmap: Dict) -> Tuple[Optional[object], Optional[str]]:
    """解析 DATE / DATETIME 值。

    Returns:
        (date/datetime 对象, 错误信息)。成功时错误信息为 None。
    """
    vtype = params.get("VALUE", "DATE-TIME").upper()
    if vtype == "DATE" or (len(value) == 8 and value.isdigit() and "-" not in value and "T" not in value):
        try:
            return date(int(value[0:4]), int(value[4:6]), int(value[6:8])), None
        except ValueError as exc:
            return None, f"非法 DATE 值: {value!r} ({exc})"
    if "T" not in value:
        return None, f"非法 DATE-TIME 值（缺少 T 分隔符）: {value!r}"
    date_part, time_part = value.split("T", 1)
    try:
        y, m, d = int(date_part[0:4]), int(date_part[4:6]), int(date_part[6:8])
        hh = int(time_part[0:2]) if len(time_part) >= 2 else 0
        mm = int(time_part[2:4]) if len(time_part) >= 4 else 0
        ss = int(time_part[4:6]) if len(time_part) >= 6 else 0
    except (ValueError, IndexError):
        return None, f"非法 DATE-TIME 值: {value!r}"
    if time_part.endswith("Z"):
        return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc), None
    tzid = params.get("TZID")
    if tzid:
        if zoneinfo is None:  # pragma: no cover
            return datetime(y, m, d, hh, mm, ss), None
        if tzid in tzmap:
            tz = tzmap[tzid]
        else:
            try:
                tz = zoneinfo.ZoneInfo(tzid)
            except Exception:
                return datetime(y, m, d, hh, mm, ss), None
        return datetime(y, m, d, hh, mm, ss, tzinfo=tz), None
    # 浮动时间（floating）：无时区信息
    return datetime(y, m, d, hh, mm, ss), None


def parse_ics_duration(value: str) -> Tuple[Optional[timedelta], Optional[str]]:
    """解析 RFC 5545 DURATION 值，例如 P1DT2H30M / -PT15M / P2W。"""
    v = value.strip()
    sign = 1
    if v.startswith("-"):
        sign = -1
        v = v[1:]
    elif v.startswith("+"):
        v = v[1:]
    if not v.startswith("P"):
        return None, f"非法 DURATION 值（缺少 P 前缀）: {value!r}"
    v = v[1:]
    weeks = days = hours = minutes = seconds = 0
    seen_t = False
    num_buf = ""
    unit_done = False
    for ch in v:
        if ch.isdigit():
            num_buf += ch
            unit_done = False
            continue
        u = ch.upper()
        if u == "T" and not seen_t and num_buf == "":
            seen_t = True  # 日期部分与时间部分的分隔符
            continue
        if num_buf == "":
            return None, f"非法 DURATION 值: {value!r}"
        n = int(num_buf)
        num_buf = ""
        if u == "W" and not seen_t:
            weeks = n
            unit_done = True
        elif u == "D" and not seen_t:
            days = n
            unit_done = True
        elif u == "T" and not seen_t:
            seen_t = True
        elif u == "H" and seen_t:
            hours = n
            unit_done = True
        elif u == "M" and seen_t:
            minutes = n
            unit_done = True
        elif u == "S" and seen_t:
            seconds = n
            unit_done = True
        else:
            return None, f"非法 DURATION 值: {value!r}"
    if not unit_done and num_buf:
        return None, f"非法 DURATION 值: {value!r}"
    return timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds) * sign, None


def _props_to_dict(params: List[Tuple[str, str]]) -> Dict[str, str]:
    d: Dict[str, str] = {}
    for k, v in params:
        d.setdefault(k, v)
    return d


def _parse_event(component_lines: List[Tuple[int, str, str, List[Tuple[str, str]], str]], tzmap: Dict) -> Event:
    """根据已切分的 VEVENT 内容行构建 Event。"""
    ev = Event()
    for line_no, _raw, name, params, value in component_lines:
        pdict = _props_to_dict(params)
        if name == "UID":
            ev.uid = value
        elif name == "SUMMARY":
            ev.summary = unescape_text(value)
        elif name == "DTSTART":
            dt, err = parse_ics_datetime(value, pdict, tzmap)
            ev.dtstart = dt
            ev.all_day = isinstance(dt, date) and not isinstance(dt, datetime)
            ev.tzid = pdict.get("TZID")
            if err:
                ev.raw["_dtstart_error"] = err
        elif name == "DTEND":
            dt, err = parse_ics_datetime(value, pdict, tzmap)
            ev.dtend = dt
            if err:
                ev.raw["_dtend_error"] = err
        elif name == "DURATION":
            dur, err = parse_ics_duration(value)
            ev.duration = dur
            if err:
                ev.raw["_duration_error"] = err
        elif name == "RRULE":
            ev.rrule_raw = value
            ev.rrule = parse_rrule_fields(value)
        elif name == "EXDATE":
            for piece in value.split(","):
                dt, _err = parse_ics_datetime(piece, pdict, tzmap)
                if dt is not None:
                    ev.exdates.append(dt)
        elif name == "RDATE":
            for piece in value.split(","):
                dt, _err = parse_ics_datetime(piece, pdict, tzmap)
                if dt is not None:
                    ev.rdates.append(dt)
        elif name == "LOCATION":
            ev.location = unescape_text(value)
        elif name == "DESCRIPTION":
            ev.description = unescape_text(value)
        elif name == "STATUS":
            ev.status = value.upper()
        elif name == "DTSTAMP":
            dt, _err = parse_ics_datetime(value, pdict, tzmap)
            if isinstance(dt, datetime):
                ev.dtstamp = dt
        elif name == "BEGIN" and value.upper() == "VALARM":
            ev.has_valarm = True
        ev.raw[name] = value
        if ev.line_no is None:
            ev.line_no = line_no
    return ev


def parse_rrule_fields(value: str) -> Dict[str, str]:
    """把 RRULE 字符串拆成大写 key -> value 字典（不做语义校验）。"""
    out: Dict[str, str] = {}
    for chunk in value.split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            out[k.strip().upper()] = v.strip().upper()
    return out


def parse_ics(text: str) -> Calendar:
    """解析 iCalendar 文本为 Calendar 对象。

    Raises:
        IcsParseError: 不含 VCALENDAR 组件等文件级错误。
    """
    lines = unfold_lines(text)
    cal = Calendar()
    split: List[Tuple[int, str, str, List[Tuple[str, str]], str]] = []
    for line_no, line in lines:
        parsed = split_content_line(line)
        if parsed is None:
            cal.parse_warnings.append(f"第 {line_no} 行无法解析为内容行，已跳过: {line[:60]!r}")
            continue
        name, params, value = parsed
        split.append((line_no, line, name, params, value))

    # 收集 VTIMEZONE 中的 TZID -> zoneinfo（尽量映射，不强制）
    if zoneinfo is not None:
        current_tzid: Optional[str] = None
        for _ln, _raw, name, params, value in split:
            if name == "BEGIN" and value.upper() == "VTIMEZONE":
                current_tzid = ""
            elif name == "END" and value.upper() == "VTIMEZONE":
                current_tzid = None
            elif current_tzid is not None and name == "TZID":
                current_tzid = value
                try:
                    cal.timezone_map[value] = zoneinfo.ZoneInfo(value)
                except Exception:
                    pass

    # 组件扫描
    stack: List[str] = []
    current_event_lines: List[Tuple[int, str, str, List[Tuple[str, str]], str]] = []
    saw_vcalendar = False
    for item in split:
        line_no, _raw, name, _params, value = item
        if name == "BEGIN":
            comp = value.upper()
            stack.append(comp)
            if comp == "VCALENDAR":
                saw_vcalendar = True
            current_event_lines = []
        elif name == "END":
            comp = value.upper()
            if stack and stack[-1] == comp:
                stack.pop()
            if comp == "VEVENT":
                cal.events.append(_parse_event(current_event_lines, cal.timezone_map))
                current_event_lines = []
            elif comp == "VTODO":
                # VTODO 以 Event 形态纳入统计（审计时标记 kind）
                todo = _parse_event(current_event_lines, cal.timezone_map)
                todo.raw["_kind"] = "VTODO"
                cal.events.append(todo)
                current_event_lines = []
        else:
            if stack and stack[-1] == "VEVENT":
                current_event_lines.append(item)
            elif stack and stack[-1] == "VTODO":
                current_event_lines.append(item)
            elif stack and stack[-1] == "VCALENDAR":
                if name == "PRODID":
                    cal.prodid = value
                elif name == "VERSION":
                    cal.version = value
                elif name == "X-WR-CALNAME":
                    cal.calname = unescape_text(value)
    if not saw_vcalendar:
        raise IcsParseError("缺少 VCALENDAR 组件：不是有效的 iCalendar 文件")
    return cal
