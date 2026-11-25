# 贡献指南 / Contributing

感谢你关注 ICSLens！本项目的硬性约束是 **零第三方依赖、完全离线、确定性输出**，请在贡献前牢记这三条底线。

## 开发环境

- Python ≥ 3.9（开发使用标准库 `unittest`，无需安装 pytest）
- 克隆后直接开发：`pip install -e .`（可选，仅为了获得 `icslens` 命令）

## 分支与提交规范

- 分支命名：`feat/xxx`、`fix/xxx`、`docs/xxx`
- 提交信息遵循 Angular 规范：

| 前缀 | 用途 |
| --- | --- |
| `feat:` | 新功能（新审计规则、新子命令） |
| `fix:` | 缺陷修复 |
| `docs:` | 文档（README、规则目录说明） |
| `refactor:` | 重构（不改行为） |
| `test:` | 测试补充 |
| `chore:` | 构建 / 杂务 |

## 新增审计规则的流程

1. 在 `icslens/audit.py` 中实现规则，编号顺延 `ICSL0xx`
2. 在同文件的 `RULE_CATALOG` 中登记编号、级别与含义
3. 在 `tests/test_core.py` 补充至少 1 条触发用例与 1 条不触发用例
4. 运行全量测试并确认通过：

```bash
python3 -m unittest discover -s tests -v
```

## 代码风格底线

- 仅允许 Python 标准库导入；`zoneinfo` 是唯一例外（3.9+ 标准库）
- 公开函数必须带 docstring 与类型注解
- 解析路径「容错优先」：坏数据不抛文件级异常，进入 `parse_warnings` 或审计发现

## 问题反馈

- 缺陷请附最小可复现的 `.ics` 片段与 `icslens audit --format json` 输出
- 功能建议请说明使用场景，便于判断是否纳入 Roadmap
