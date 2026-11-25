<div align="center">

# 🔬 ICSLens

**零相依 · 離線優先的 iCalendar (RFC 5545) 解析、重複事件展開與行事曆健康度稽核引擎**

Python 函式庫 + CLI 雙形態 · 15 條稽核規則 · 4 種報告格式 · CI 閘門就緒

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/Tests-30%20passed-brightgreen.svg)](tests/)

[简体中文](README.md) · 繁體中文 · [English](README.en.md)

</div>

---

## 🎉 介紹

`.ics` 行事曆檔案無所不在：郵件附件、會議邀請、行事曆訂閱、系統匯出……但它也是出了名的「格式陷阱重災區」——**結束時間填反、缺 UID、COUNT 與 UNTIL 並存、浮動時間遇上日光節約時間、TZID 誰也不認識**。這些問題往往直到同步遺失或行程顯示錯亂才被發現。

**ICSLens** 用一把純標準庫的手術刀解決這一切：完整解析 RFC 5545 文本、自研展開重複規則（RRULE）、再用 15 條稽核規則把行事曆的每個坑揪出來，並直接輸出可用於 CI 閘門的報告。

> 💡 核心設計：**零第三方相依**（僅用 Python 3.9+ 標準庫 `zoneinfo`）、**完全離線**、**確定性輸出**——同一個檔案在任何機器上得到完全一致的結果。

## ✨ 特性

| 模組 | 能力 |
| --- | --- |
| 🧩 **解析器** | RFC 5545 行展開（folding）、引號感知參數切分、TEXT 反轉義、`TZID` ↔ IANA 時區映射 |
| 🔁 **重複引擎** | 自研 RRULE 展開：`DAILY / WEEKLY / MONTHLY / YEARLY`、`INTERVAL / COUNT / UNTIL / BYDAY / BYMONTHDAY / BYMONTH`、`EXDATE / RDATE`，內建 **5000 次安全上限** 防失控 |
| 🛡️ **稽核規則** | 15 條規則（ICSL001~015）：缺 UID、缺 DTSTAMP、結束早於開始、COUNT+UNTIL 並存、重複 UID、時區陷阱、無限重複失控……ERROR/WARNING/INFO 三級分類 |
| 📊 **負載統計** | 事件量、總時長、最忙碌的 5 天、高發時段 TOP5、最長單項，時區感知聚合 |
| 📤 **報告輸出** | `text` / `json` / `csv` / `markdown` 四種格式；`--fail-on error` 直接接入 CI 閘門（結束代碼 1） |
| ⚙️ **雙形態** | `python -m icslens` / `icslens` 命令列 + `import icslens` 函式庫呼叫，同一引擎 |

## 🚀 快速開始

```bash
# 從 PyPI 安裝（或見下方「📦 打包部署」原始碼安裝）
pip install icslens

# 三秒上手：稽核一個行事曆檔案
icslens audit your-calendar.ics

# CI 閘門：存在 error 級問題時結束代碼為 1
icslens audit your-calendar.ics --fail-on error
```

零安裝直接執行（無需 pip）：

```bash
python3 -m icslens.cli audit your-calendar.ics
```

## 📖 使用指南

### 🛡️ 命令列：稽核

```bash
icslens audit examples/team.ics                    # 終端友善文字報告
icslens audit examples/team.ics --format json      # JSON（供程式消費）
icslens audit examples/team.ics --format md        # Markdown（貼進 PR/Issue）
icslens audit examples/team.ics --format csv       # CSV（進表格分析）
icslens audit examples/team.ics --no-expansion     # 跳過 RRULE 展開（更快）
cat merged.ics | icslens audit -                   # stdin 串流輸入
```

### 🔁 命令列：展開重複事件

```bash
# 檢視某個重複事件在一個時間窗內的所有發生時刻
icslens expand team.ics --uid sprint-review@demo.example \
    --from 2026-11-01 --to 2027-01-31
```

### 📊 命令列：行事曆負載統計

```bash
icslens stats team.ics --tz Asia/Taipei
```

### 🧩 規則目錄

```bash
icslens rules   # 印出 ICSL001~015 全部規則及級別
```

### 🐍 Python 函式庫呼叫

```python
import json
import icslens
from icslens.audit import audit
from icslens.rrule import expand_rrule
from icslens.stats import stats

with open("calendar.ics", encoding="utf-8") as fh:
    cal = icslens.parse_ics(fh.read())

# 1) 稽核：拿結構化發現做你自己的閘門
findings = audit(cal)
for f in findings:
    print(f.rule_id, f.severity.value, f.message)

# 2) 展開重複事件（aware/naive datetime 均支援）
occurrences = expand_rrule(
    cal.events[0].dtstart, cal.events[0].rrule, cal.events[0].exdates
)

# 3) 負載統計
print(json.dumps(stats(cal), ensure_ascii=False, indent=2))
```

### 🔗 CI 整合範例（GitHub Actions）

```yaml
- name: Calendar health gate
  run: pip install icslens && icslens audit calendar/team.ics --fail-on warning
```

## 💡 設計迭代

- **v1.0.0（目前）**：解析器 + RRULE 引擎 + 15 條稽核規則 + 4 種報告 + CI 閘門 + 負載統計，30 個單元測試全數通過。
- **Roadmap**：
  - `VTIMEZONE` 自訂時區定義的完整解析（目前僅映射標準 IANA 時區）
  - `BYSETPOS`、`SECONDLY / MINUTELY / HOURLY` 等冷門頻率
  - 事件去重與行事曆合併（merge + dedupe 子命令）
  - 大檔案串流解析（目前為一次性載入）

## 📦 打包部署

```bash
# 原始碼安裝（開發模式）
git clone https://github.com/gitstq/icslens.git && cd icslens
pip install -e .

# 建置發行包（sdist + wheel）
pip install build && python -m build

# 執行全部單元測試（30 個，純標準庫，無需 pytest）
python3 -m unittest discover -s tests -v
```

## 🤝 貢獻

歡迎 Issue 與 PR！

1. Fork → 新建分支 `feat/your-feature`
2. 提交遵循 [Angular 規範](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)：`feat:` / `fix:` / `docs:` / `refactor:` / `test:`
3. 確保全部測試通過：`python3 -m unittest discover -s tests`
4. 新增稽核規則請同步更新 `audit.py` 的 `RULE_CATALOG` 與測試

詳見 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 授權條款

[MIT](LICENSE) © gitstq —— 放心整合到任何專案。
