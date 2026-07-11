# CHANGELOG

## 2026-07-09

### Excel loader update

1. Implemented the first V1 reading path for `data_private/depth.xls` and `data_private/temp.xls`.
2. Added Excel-only loader logic in `src/loaders.py`.
3. Added column alias resolution for datetime and value columns.
4. Normalized loaded data to `datetime` and `value`.
5. Added sorting by `datetime` during load.
6. Confirmed the current private files use columns `时间` and `值`.
7. Installed and used `xlrd` for legacy `.xls` reading.

### Architecture update

1. Added V1 architecture documentation under `docs/`.
2. Changed V1 input architecture to Excel-only.
3. Marked MAT file support as V2 only.
4. Limited V1 variables to `depth` and `temperature`.
5. Excluded harmonic analysis, water-quality variables, and AI report generation from V1.
6. Added placeholder modules under `src/` for loaders, registry, QC, resampling, anomaly, metrics, plotting, report tables, and non-AI report text.
7. Added variable metadata placeholders in `src/variable_registry.py`.

### Note

`PRD.md` still contains older planning content from the previous V1 decision. The current V1 architecture source of truth is now the `docs/` architecture set created in this update.

### Changed

1. 将原 PRD 收敛为 2-3 周可完成的本地 Streamlit V1 Demo。
2. 把功能拆分为 V1 必做、V1.5 可选和未来功能。
3. 明确 V1 只支持单个标准 CSV、单站点、单变量、单时间范围分析。
4. 移除 V1 中过宽的范围：Excel 导入、批量处理、异常图、地图、数据库、权限系统、云端部署和复杂模型。
5. 新增标准输入数据 Schema，包括必填字段、可选字段和输入限制。
6. 明确所有数值必须由确定性 MATLAB 或 Python 逻辑计算，AI 只能基于统计 JSON 生成文字。
7. 新增可量化验收标准，包括 50,000 行数据、10 秒分析耗时、重复运行一致性和 AI 越界率为 0。
8. 新增数据隐私、AI 幻觉、数据质量和报告可靠性相关风险。
9. 重写最终 MVP 范围，使其更短、更可执行、更适合本地演示。

### Notes

当前目录中未发现旧的 `PRD.md` 文件。本次以已有的 `PRD-AI环境监测分析报告工具.md` 作为审计来源，并输出新的 `PRD.md`。
