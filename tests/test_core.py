"""ICSLens 核心功能单元测试（纯标准库 unittest）。"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from icslens.parser import (  # noqa: E402
    IcsParseError,
    parse_ics,
    parse_ics_duration,
    parse_ics_datetime,
    split_content_line,
    unescape_text,
    unfold_lines,
)
from icslens.rrule import RruleError, expand_rrule  # noqa: E402
from icslens.audit import audit  # noqa: E402
from icslens.model import Severity  # noqa: E402
from icslens.report import fail_exit_code, findings_to_csv, findings_to_json, findings_to_markdown  # noqa: E402
from icslens.stats import stats  # noqa: E402

SAMPLE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example//Cal 1.0//EN
X-WR-CALNAME:测试日历
BEGIN:VEVENT
UID:evt-001@example.com
DTSTAMP:20260101T000000Z
SUMMARY:周会\\n（含换行）
DTSTART;TZID=Asia/Shanghai:20260105T100000
DTEND;TZID=Asia/Shanghai:20260105T110000
RRULE:FREQ=WEEKLY;COUNT=4
LOCATION:会议室 A\\, 3F
END:VEVENT
BEGIN:VEVENT
UID:evt-002@example.com
DTSTAMP:20260101T000000Z
SUMMARY:全天活动
DTSTART;VALUE=DATE:20260210
DTEND;VALUE=DATE:20260212
END:VEVENT
END:VCALENDAR
"""


class TestParser(unittest.TestCase):
    def test_unfold_lines(self):
        # RFC 5545 折叠 = 插入 CRLF + 单个空白；展开 = 移除 CRLF 与该空白
        text = "SUMMARY:hello\r\n world\r\nDTSTART:20260101T000000Z\r\n"
        lines = unfold_lines(text)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0][1], "SUMMARY:helloworld")
        # 原文含空格时折叠需双倍空白才能无损还原
        text2 = "DESCRIPTION:hello\r\n  world\r\n"
        lines2 = unfold_lines(text2)
        self.assertEqual(lines2[0][1], "DESCRIPTION:hello world")

    def test_split_line_with_quoted_colon(self):
        parsed = split_content_line('ATTENDEE;CN="Zhang, San":mailto:a@b.com')
        self.assertIsNotNone(parsed)
        name, params, value = parsed
        self.assertEqual(name, "ATTENDEE")
        self.assertEqual(params, [("CN", "Zhang, San")])
        self.assertEqual(value, "mailto:a@b.com")

    def test_unescape_text(self):
        self.assertEqual(unescape_text("a\\,b\\;c\\nd\\\\e"), "a,b;c\nd\\e")

    def test_parse_duration(self):
        self.assertEqual(parse_ics_duration("PT1H30M")[0], timedelta(hours=1, minutes=30))
        self.assertEqual(parse_ics_duration("P1DT2H")[0], timedelta(days=1, hours=2))
        self.assertEqual(parse_ics_duration("-PT15M")[0], timedelta(minutes=-15))
        self.assertEqual(parse_ics_duration("P2W")[0], timedelta(weeks=2))
        self.assertIsNone(parse_ics_duration("XYZ")[0])

    def test_parse_datetime_variants(self):
        dt, err = parse_ics_datetime("20260105T100000Z", {}, {})
        self.assertIsNone(err)
        self.assertEqual(dt.utcoffset(), timedelta(0))
        d, err = parse_ics_datetime("20260210", {}, {})
        self.assertIsNone(err)
        self.assertEqual(d, date(2026, 2, 10))

    def test_parse_sample(self):
        cal = parse_ics(SAMPLE)
        self.assertEqual(cal.event_count, 2)
        self.assertEqual(cal.calname, "测试日历")
        ev1 = cal.events[0]
        self.assertEqual(ev1.uid, "evt-001@example.com")
        self.assertEqual(ev1.summary, "周会\n（含换行）")
        self.assertEqual(ev1.location, "会议室 A, 3F")
        self.assertTrue(ev1.rrule["FREQ"] == "WEEKLY")
        self.assertTrue(cal.events[1].all_day)

    def test_missing_vcalendar_raises(self):
        with self.assertRaises(IcsParseError):
            parse_ics("BEGIN:VEVENT\nEND:VEVENT\n")

    def test_broken_line_collected_as_warning(self):
        cal = parse_ics("BEGIN:VCALENDAR\nnot-a-line\nEND:VCALENDAR\n")
        self.assertTrue(any("无法解析" in w for w in cal.parse_warnings))


class TestRrule(unittest.TestCase):
    def test_daily_count(self):
        start = datetime(2026, 1, 1, 9, 0)
        occ = expand_rrule(start, {"FREQ": "DAILY", "COUNT": "5"})
        self.assertEqual(len(occ), 5)
        self.assertEqual(occ[-1], datetime(2026, 1, 5, 9, 0))

    def test_daily_interval(self):
        start = date(2026, 1, 1)
        occ = expand_rrule(start, {"FREQ": "DAILY", "INTERVAL": "3", "COUNT": "3"})
        self.assertEqual([o for o in occ], [date(2026, 1, 1), date(2026, 1, 4), date(2026, 1, 7)])

    def test_weekly_byday(self):
        start = datetime(2026, 1, 5, 10, 0)  # 周一
        occ = expand_rrule(start, {"FREQ": "WEEKLY", "BYDAY": "MO,WE", "COUNT": "4"})
        self.assertEqual(len(occ), 4)
        self.assertEqual({o.weekday() for o in occ}, {0, 2})
        self.assertEqual(occ[1].weekday(), 2)  # 第一个周三

    def test_monthly_nth_weekday(self):
        start = date(2026, 1, 1)
        occ = expand_rrule(start, {"FREQ": "MONTHLY", "BYDAY": "1FR", "COUNT": "3"})
        self.assertEqual(occ[0], date(2026, 1, 2))   # 1 月第一个周五
        self.assertEqual(occ[1], date(2026, 2, 6))   # 2 月第一个周五
        self.assertEqual(occ[2], date(2026, 3, 6))   # 3 月第一个周五

    def test_monthly_last_day(self):
        start = date(2026, 1, 31)
        occ = expand_rrule(start, {"FREQ": "MONTHLY", "BYMONTHDAY": "-1", "COUNT": "3"})
        self.assertEqual([o.day for o in occ], [31, 28, 31])  # 1/2/3 月最后一天

    def test_yearly_bymonth(self):
        start = date(2026, 3, 15)
        occ = expand_rrule(start, {"FREQ": "YEARLY", "BYMONTH": "3,6", "COUNT": "4"})
        self.assertEqual([o.month for o in occ], [3, 6, 3, 6])
        self.assertEqual(occ[0].year, 2026)
        self.assertEqual(occ[2].year, 2027)

    def test_until(self):
        start = datetime(2026, 1, 1, 8, 0)
        occ = expand_rrule(start, {"FREQ": "DAILY", "UNTIL": "20260104T080000Z"})
        self.assertEqual(len(occ), 4)

    def test_exdate(self):
        start = datetime(2026, 1, 1, 8, 0)
        ex = [datetime(2026, 1, 3, 8, 0)]
        occ = expand_rrule(start, {"FREQ": "DAILY", "COUNT": "5"}, exdates=ex)
        self.assertEqual(len(occ), 4)
        self.assertNotIn(datetime(2026, 1, 3, 8, 0), occ)

    def test_unsupported_freq(self):
        with self.assertRaises(RruleError):
            expand_rrule(datetime(2026, 1, 1), {"FREQ": "SECONDLY"})

    def test_safety_cap(self):
        start = datetime(2026, 1, 1, 8, 0)
        occ = expand_rrule(start, {"FREQ": "DAILY"})
        self.assertEqual(len(occ), 5000)  # 安全上限


class TestAudit(unittest.TestCase):
    def _audit_text(self, text):
        return audit(parse_ics(text))

    def test_missing_uid_error(self):
        findings = self._audit_text(
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//x//EN\nBEGIN:VEVENT\n"
            "DTSTAMP:20260101T000000Z\nSUMMARY:x\nDTSTART:20260101T090000Z\nDTEND:20260101T100000Z\n"
            "END:VEVENT\nEND:VCALENDAR\n"
        )
        self.assertTrue(any(f.rule_id == "ICSL001" and f.severity == Severity.ERROR for f in findings))

    def test_duplicate_uid(self):
        text = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//x//EN\n"
            "BEGIN:VEVENT\nUID:a@x\nDTSTAMP:20260101T000000Z\nSUMMARY:1\n"
            "DTSTART:20260101T090000Z\nDTEND:20260101T100000Z\nEND:VEVENT\n"
            "BEGIN:VEVENT\nUID:a@x\nDTSTAMP:20260101T000000Z\nSUMMARY:2\n"
            "DTSTART:20260101T090000Z\nDTEND:20260101T100000Z\nEND:VEVENT\n"
            "END:VCALENDAR\n"
        )
        findings = self._audit_text(text)
        self.assertTrue(any(f.rule_id == "ICSL008" for f in findings))

    def test_end_before_start(self):
        text = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//x//EN\n"
            "BEGIN:VEVENT\nUID:b@x\nDTSTAMP:20260101T000000Z\nSUMMARY:x\n"
            "DTSTART:20260101T100000Z\nDTEND:20260101T090000Z\nEND:VEVENT\n"
            "END:VCALENDAR\n"
        )
        findings = self._audit_text(text)
        self.assertTrue(any(f.rule_id == "ICSL005" for f in findings))

    def test_count_and_until_both(self):
        text = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//x//EN\n"
            "BEGIN:VEVENT\nUID:c@x\nDTSTAMP:20260101T000000Z\nSUMMARY:x\n"
            "DTSTART:20260101T100000Z\nDTEND:20260101T110000Z\n"
            "RRULE:FREQ=DAILY;COUNT=3;UNTIL=20260105T000000Z\nEND:VEVENT\n"
            "END:VCALENDAR\n"
        )
        findings = self._audit_text(text)
        self.assertTrue(any(f.rule_id == "ICSL009" for f in findings))

    def test_clean_sample_only_minor(self):
        findings = self._audit_text(SAMPLE)
        errors = [f for f in findings if f.severity == Severity.ERROR]
        self.assertEqual(errors, [])

    def test_bad_tzid(self):
        text = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//x//EN\n"
            "BEGIN:VEVENT\nUID:d@x\nDTSTAMP:20260101T000000Z\nSUMMARY:x\n"
            "DTSTART;TZID=Not/AZone:20260101T090000\nDTEND;TZID=Not/AZone:20260101T100000\n"
            "END:VEVENT\nEND:VCALENDAR\n"
        )
        findings = self._audit_text(text)
        self.assertTrue(any(f.rule_id == "ICSL014" for f in findings))


class TestReportAndGate(unittest.TestCase):
    def test_fail_on_error(self):
        from icslens.model import Finding
        f_err = Finding("ICSL001", Severity.ERROR, "x")
        f_info = Finding("ICSL010", Severity.INFO, "y")
        self.assertEqual(fail_exit_code([f_err], "error"), 1)
        self.assertIsNone(fail_exit_code([f_info], "error"))
        self.assertEqual(fail_exit_code([f_info], "info"), 1)

    def test_outputs_render(self):
        from icslens.model import Finding
        f = Finding("ICSL002", Severity.WARNING, "缺 DTSTAMP", uid="a@x", line_no=3)
        self.assertIn("ICSL002", findings_to_json([f]))
        self.assertIn("warning", findings_to_csv([f]))
        self.assertIn("ICSL002", findings_to_markdown([f]))

    def test_stats(self):
        cal = parse_ics(SAMPLE)
        s = stats(cal)
        self.assertEqual(s["event_count"], 2)
        self.assertEqual(s["recurring_events"], 1)
        self.assertGreater(s["total_minutes"], 0)


class TestCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "icslens.cli", *args],
            capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), ".."),
        )

    def test_cli_audit_text_and_gate(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False) as fh:
            fh.write(SAMPLE)
            path = fh.name
        try:
            r = self._run("audit", path, "--format", "json")
            self.assertEqual(r.returncode, 0)
            self.assertIn("findings", r.stdout)
            r2 = self._run("audit", path, "--fail-on", "warning")
            # SAMPLE 存在 warning 级别问题吗？样本是干净的 —— 退出码应为 0
            self.assertEqual(r2.returncode, 0)
        finally:
            os.unlink(path)

    def test_cli_stats_and_rules(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False) as fh:
            fh.write(SAMPLE)
            path = fh.name
        try:
            r = self._run("stats", path)
            self.assertEqual(r.returncode, 0)
            self.assertIn("事件总数", r.stdout)
        finally:
            os.unlink(path)
        r3 = self._run("rules")
        self.assertEqual(r3.returncode, 0)
        self.assertIn("ICSL001", r3.stdout)

    def test_cli_expand(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False) as fh:
            fh.write(SAMPLE)
            path = fh.name
        try:
            r = self._run("expand", path, "--uid", "evt-001@example.com")
            self.assertEqual(r.returncode, 0)
            self.assertIn("occurrences", r.stdout)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
