<div align="center">

# 🔬 ICSLens

**零依赖 · 离线优先的 iCalendar (RFC 5545) 解析、重复事件展开与日历健康审计引擎**

Python 库 + CLI 双形态 · 15 条审计规则 · 4 种报告格式 · CI 门禁就绪

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/Tests-30%20passed-brightgreen.svg)](tests/)

简体中文 · [繁體中文](README.zh-TW.md) · [English](README.en.md)

</div>

---

## 🎉 介绍

`.ics` 日历文件无处不在：邮件附件、会议邀请、日历订阅、系统导出……但它也是出了名的「格式陷阱重灾区」——**结束时间填反、缺 UID、COUNT 与 UNTIL 并存、浮动时间遇上夏令时、TZID 谁也不认识**。这些问题往往直到同步丢失或日程显示错乱才被发现。

**ICSLens** 用一把纯标准库的手术刀解决这一切：完整解析 RFC 5545 文本、自研展开重复规则（RRULE）、再用 15 条审计规则把日历的每个坑揪出来，并直接输出可用于 CI 门禁的报告。

> 💡 核心设计：**零第三方依赖**（仅用 Python 3.9+ 标准库 `zoneinfo`）、**完全离线**、**确定性输出**——同一个文件在任何机器上得到完全一致的结果。

## ✨ 特性

| 模块 | 能力 |
| --- | --- |
| 🧩 **解析器** | RFC 5545 行展开（folding）、引号感知参数切分、TEXT 反转义、`TZID` ↔ IANA 时区映射 |
| 🔁 **重复引擎** | 自研 RRULE 展开：`DAILY / WEEKLY / MONTHLY / YEARLY`、`INTERVAL / COUNT / UNTIL / BYDAY / BYMONTHDAY / BYMONTH`、`EXDATE / RDATE`，内置 **5000 次安全上限** 防失控 |
| 🛡️ **审计规则** | 15 条规则（ICSL001~015）：缺 UID、缺 DTSTAMP、结束早于开始、COUNT+UNTIL 并存、重复 UID、时区陷阱、无限重复失控……ERROR/WARNING/INFO 三级分类 |
| 📊 **负载统计** | 事件量、总时长、最忙碌的 5 天、高发时段 TOP5、最长单项，时区感知聚合 |
| 📤 **报告输出** | `text` / `json` / `csv` / `markdown` 四种格式；`--fail-on error` 直接接入 CI 门禁（退出码 1） |
| ⚙️ **双形态** | `python -m icslens` / `icslens` 命令行 + `import icslens` 库调用，同一引擎 |

## 🚀 快速开始

```bash
# 从 PyPI 安装（或见下方「📦 打包部署」源码安装）
pip install icslens

# 三秒上手：审计一个日历文件
icslens audit your-calendar.ics

# CI 门禁：存在 error 级问题时退出码为 1
icslens audit your-calendar.ics --fail-on error
```

零安装直接运行（无需 pip）：

```bash
python3 -m icslens.cli audit your-calendar.ics
```

## 📖 使用指南

### 🛡️ 命令行：审计

```bash
icslens audit examples/team.ics                    # 终端友好文本报告
icslens audit examples/team.ics --format json      # JSON（供程序消费）
icslens audit examples/team.ics --format md        # Markdown（贴进 PR/Issue）
icslens audit examples/team.ics --format csv       # CSV（进表格分析）
icslens audit examples/team.ics --no-expansion     # 跳过 RRULE 展开（更快）
cat merged.ics | icslens audit -                   # stdin 流式输入
```

### 🔁 命令行：展开重复事件

```bash
# 查看某个重复事件在一个时间窗内的所有发生时刻
icslens expand team.ics --uid sprint-review@demo.example \
    --from 2026-11-01 --to 2027-01-31
```

### 📊 命令行：日历负载统计

```bash
icslens stats team.ics --tz Asia/Shanghai
```

### 🧩 规则目录

```bash
icslens rules   # 打印 ICSL001~015 全部规则及级别
```

### 🐍 Python 库调用

```python
import json
import icslens
from icslens.audit import audit
from icslens.rrule import expand_rrule
from icslens.stats import stats

with open("calendar.ics", encoding="utf-8") as fh:
    cal = icslens.parse_ics(fh.read())

# 1) 审计：拿结构化发现做你自己的门禁
findings = audit(cal)
for f in findings:
    print(f.rule_id, f.severity.value, f.message)

# 2) 展开重复事件（ aware/naive datetime 均支持）
occurrences = expand_rrule(
    cal.events[0].dtstart, cal.events[0].rrule, cal.events[0].exdates
)

# 3) 负载统计
print(json.dumps(stats(cal), ensure_ascii=False, indent=2))
```

### 🔗 CI 集成示例（GitHub Actions）

```yaml
- name: Calendar health gate
  run: pip install icslens && icslens audit calendar/team.ics --fail-on warning
```

## 💡 设计迭代

- **v1.0.0（当前）**：解析器 + RRULE 引擎 + 15 条审计规则 + 4 种报告 + CI 门禁 + 负载统计，30 个单元测试全绿。
- ** Roadmap**：
  - `VTIMEZONE` 自定义时区定义的完整解析（当前仅映射标准 IANA 时区）
  - `BYSETPOS`、`SECONDLY / MINUTELY / HOURLY` 等冷门频率
  - 事件去重与日历合并（merge + dedupe 子命令）
  - 大文件流式解析（当前为一次性载入）

## 📦 打包部署

```bash
# 源码安装（开发模式）
git clone https://github.com/gitstq/icslens.git && cd icslens
pip install -e .

# 构建分发包（sdist + wheel）
pip install build && python -m build

# 运行全部单元测试（30 个，纯标准库，无需 pytest）
python3 -m unittest discover -s tests -v
```

## 🤝 贡献

欢迎 Issue 与 PR！

1. Fork → 新建分支 `feat/your-feature`
2. 提交遵循 [Angular 规范](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)：`feat:` / `fix:` / `docs:` / `refactor:` / `test:`
3. 确保全部测试通过：`python3 -m unittest discover -s tests`
4. 新增审计规则请同步更新 `audit.py` 的 `RULE_CATALOG` 与测试

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 协议

[MIT](LICENSE) © gitstq —— 放心集成到任何项目。
