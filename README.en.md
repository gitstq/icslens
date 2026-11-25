<div align="center">

# 🔬 ICSLens

**Zero-dependency, offline-first iCalendar (RFC 5545) parser, recurrence expander & calendar health auditor**

Python library + CLI · 15 audit rules · 4 report formats · CI-gate ready

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/Tests-30%20passed-brightgreen.svg)](tests/)

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · English

</div>

---

## 🎉 Introduction

`.ics` calendar files are everywhere — email attachments, meeting invites, calendar subscriptions, system exports. They are also a notorious minefield of format traps: **swapped start/end times, missing UIDs, COUNT paired with UNTIL, floating times colliding with DST, TZIDs nobody can resolve**. These issues usually surface only after a sync loses events or schedules display wrongly.

**ICSLens** solves all of this with a pure-stdlib scalpel: it fully parses RFC 5545 text, expands recurrence rules (RRULE) with its own engine, then runs 15 audit rules to surface every pitfall — and emits reports that plug straight into CI gates.

> 💡 Core design: **zero third-party dependencies** (only Python 3.9+ stdlib `zoneinfo`), **fully offline**, **deterministic output** — the same file yields byte-identical results on any machine.

## ✨ Features

| Module | Capabilities |
| --- | --- |
| 🧩 **Parser** | RFC 5545 line unfolding (folding), quote-aware parameter splitting, TEXT unescaping, `TZID` ↔ IANA timezone mapping |
| 🔁 **Recurrence engine** | Home-grown RRULE expansion: `DAILY / WEEKLY / MONTHLY / YEARLY`, `INTERVAL / COUNT / UNTIL / BYDAY / BYMONTHDAY / BYMONTH`, `EXDATE / RDATE`, with a **5000-occurrence safety cap** |
| 🛡️ **Audit rules** | 15 rules (ICSL001~015): missing UID, missing DTSTAMP, end-before-start, COUNT+UNTIL together, duplicate UID, timezone traps, runaway infinite recurrences… classified as ERROR/WARNING/INFO |
| 📊 **Load analytics** | Event count, total duration, 5 busiest days, peak hours top 5, longest single item — timezone-aware aggregation |
| 📤 **Report output** | `text` / `json` / `csv` / `markdown`; `--fail-on error` plugs into CI gates (exit code 1) |
| ⚙️ **Dual form** | `python -m icslens` / `icslens` CLI + `import icslens` library, same engine |

## 🚀 Quick Start

```bash
# Install from PyPI (or see "📦 Packaging & Deployment" for source install)
pip install icslens

# Up and running in 3 seconds: audit a calendar file
icslens audit your-calendar.ics

# CI gate: exit code 1 when any error-level finding exists
icslens audit your-calendar.ics --fail-on error
```

Run without installing (no pip needed):

```bash
python3 -m icslens.cli audit your-calendar.ics
```

## 📖 Usage Guide

### 🛡️ CLI: Audit

```bash
icslens audit examples/team.ics                    # terminal-friendly text report
icslens audit examples/team.ics --format json      # JSON (machine-readable)
icslens audit examples/team.ics --format md        # Markdown (paste into PR/Issue)
icslens audit examples/team.ics --format csv       # CSV (spreadsheet analysis)
icslens audit examples/team.ics --no-expansion     # skip RRULE expansion (faster)
cat merged.ics | icslens audit -                   # streaming via stdin
```

### 🔁 CLI: Expand recurrences

```bash
# List every occurrence of a recurring event within a time window
icslens expand team.ics --uid sprint-review@demo.example \
    --from 2026-11-01 --to 2027-01-31
```

### 📊 CLI: Calendar load analytics

```bash
icslens stats team.ics --tz Asia/Shanghai
```

### 🧩 Rule catalog

```bash
icslens rules   # print all rules ICSL001~015 with severities
```

### 🐍 Python library

```python
import json
import icslens
from icslens.audit import audit
from icslens.rrule import expand_rrule
from icslens.stats import stats

with open("calendar.ics", encoding="utf-8") as fh:
    cal = icslens.parse_ics(fh.read())

# 1) Audit: consume structured findings in your own gate
findings = audit(cal)
for f in findings:
    print(f.rule_id, f.severity.value, f.message)

# 2) Expand a recurrence (aware and naive datetimes both supported)
occurrences = expand_rrule(
    cal.events[0].dtstart, cal.events[0].rrule, cal.events[0].exdates
)

# 3) Load analytics
print(json.dumps(stats(cal), ensure_ascii=False, indent=2))
```

### 🔗 CI integration example (GitHub Actions)

```yaml
- name: Calendar health gate
  run: pip install icslens && icslens audit calendar/team.ics --fail-on warning
```

## 💡 Design Iterations

- **v1.0.0 (current)**: parser + RRULE engine + 15 audit rules + 4 report formats + CI gate + load analytics; all 30 unit tests green.
- **Roadmap**:
  - Full parsing of custom `VTIMEZONE` definitions (currently maps standard IANA timezones only)
  - Niche frequencies such as `BYSETPOS`, `SECONDLY / MINUTELY / HOURLY`
  - Event dedup & calendar merge (`merge` + `dedupe` subcommands)
  - Streaming parse for very large files (currently single-pass load)

## 📦 Packaging & Deployment

```bash
# Source install (dev mode)
git clone https://github.com/gitstq/icslens.git && cd icslens
pip install -e .

# Build distribution packages (sdist + wheel)
pip install build && python -m build

# Run the full test suite (30 tests, pure stdlib, pytest not required)
python3 -m unittest discover -s tests -v
```

## 🤝 Contributing

Issues and PRs are welcome!

1. Fork → create branch `feat/your-feature`
2. Follow the [Angular commit convention](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit): `feat:` / `fix:` / `docs:` / `refactor:` / `test:`
3. Make sure all tests pass: `python3 -m unittest discover -s tests`
4. When adding an audit rule, also update `RULE_CATALOG` in `audit.py` and the tests

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📄 License

[MIT](LICENSE) © gitstq — safe to embed in any project.
