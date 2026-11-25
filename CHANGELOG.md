# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)，提交信息遵循 Angular 规范。

## [1.0.0] - 2026-11-25

### Added
- 🧩 RFC 5545 解析器：行展开、引号感知参数切分、TEXT 反转义、TZID ↔ IANA 时区映射
- 🔁 自研 RRULE 展开引擎：DAILY/WEEKLY/MONTHLY/YEARLY × INTERVAL/COUNT/UNTIL/BYDAY/BYMONTHDAY/BYMONTH，支持 EXDATE/RDATE 与 5000 次安全上限
- 🛡️ 15 条日历健康审计规则（ICSL001~015），ERROR/WARNING/INFO 三级
- 📊 日历负载统计：忙碌日、高发时段、最长单项、时区感知聚合
- 📤 text/json/csv/markdown 四种报告格式与 `--fail-on` CI 门禁
- ⚙️ `icslens` CLI（audit / expand / stats / rules）与 Python 库双形态
- ✅ 30 个单元测试（纯标准库 unittest）
