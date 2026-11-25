"""日历负载统计分析：事件量、总时长、忙碌日、最长会议等。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .model import Calendar


def stats(cal: Calendar, timezone_hint: Optional[str] = None) -> Dict[str, Any]:
    """计算日历统计信息，输出可 JSON 序列化的字典。"""
    events = [e for e in cal.events if e.dtstart is not None]
    counted = 0
    total_minutes = 0.0
    by_day: Dict[str, float] = defaultdict(float)
    by_hour: Counter = Counter()
    longest = None  # (minutes, summary, dtstart)
    all_day_count = 0
    recurring_count = 0

    for ev in events:
        counted += 1
        if ev.all_day:
            all_day_count += 1
        if ev.rrule:
            recurring_count += 1
        mins = ev.duration_minutes() or 0.0
        total_minutes += mins
        if isinstance(ev.dtstart, datetime):
            local = ev.dtstart
            if timezone_hint:
                try:
                    import zoneinfo
                    local = ev.dtstart.astimezone(zoneinfo.ZoneInfo(timezone_hint))
                except Exception:
                    pass
            day_key = local.strftime("%Y-%m-%d")
            by_hour[local.hour] += 1
        else:
            day_key = ev.dtstart.strftime("%Y-%m-%d")
        by_day[day_key] += mins
        if mins > 0 and (longest is None or mins > longest[0]):
            longest = (mins, ev.summary or "(无标题)", _iso(ev.dtstart))

    busiest_days = sorted(by_day.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    peak_hours = by_hour.most_common(5)

    return {
        "calendar_name": cal.calname,
        "prodid": cal.prodid,
        "event_count": counted,
        "all_day_events": all_day_count,
        "recurring_events": recurring_count,
        "total_minutes": round(total_minutes, 1),
        "total_hours": round(total_minutes / 60.0, 2),
        "busiest_days": [
            {"date": d, "minutes": round(m, 1)} for d, m in busiest_days
        ],
        "peak_hours": [{"hour": h, "events": c} for h, c in peak_hours],
        "longest_event": (
            {"minutes": round(longest[0], 1), "summary": longest[1], "start": longest[2]}
            if longest else None
        ),
    }


def render_stats_text(s: Dict[str, Any]) -> str:
    """把统计结果渲染为终端友好文本。"""
    lines = []
    name = s.get("calendar_name") or "(未命名日历)"
    lines.append(f"📅 日历: {name}")
    lines.append(f"🔢 事件总数: {s['event_count']}（全天 {s['all_day_events']} · 重复 {s['recurring_events']}）")
    hours = s["total_hours"]
    lines.append(f"⏱️  总时长: {hours:g} 小时（{s['total_minutes']:g} 分钟）")
    if s["busiest_days"]:
        lines.append("🔥 最忙碌的 5 天:")
        for item in s["busiest_days"]:
            lines.append(f"   {item['date']}  {item['minutes']:g} 分钟")
    if s["peak_hours"]:
        lines.append("🕐 高发时段 TOP5:")
        for item in s["peak_hours"]:
            lines.append(f"   {item['hour']:02d}:00 时段  {item['events']} 场")
    if s.get("longest_event"):
        le = s["longest_event"]
        lines.append(f"🏆 最长单项: {le['summary']}（{le['minutes']:g} 分钟, 开始 {le['start']}）")
    return "\n".join(lines)


def _iso(obj) -> str:
    return obj.isoformat() if hasattr(obj, "isoformat") else str(obj)
