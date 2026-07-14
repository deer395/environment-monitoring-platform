# 当前分支

feature/v3-general-variables

# 当前已完成

- V2 质量控制闭环；
- V3.1 通用变量架构；
- V3.2 接入 salinity、dissolved_oxygen、cod；
- V3.2.1 完成 hard_range 与候选图背景线修复；
- V3.3 接入 bod、nitrate、chlorophyll、pahs；
- V3.4 完成最终验收、导出可靠性修复和文档收尾。

# 当前 Git 基线

- `v2-qc-complete`
- `v3.1-generic-architecture`
- `v3.2-three-variable-validation`
- `v3.2.1-qc-interaction-complete`
- `v3.3-all-variables-complete`

# V3.4 说明

- 当前支持九个变量：depth、temperature、salinity、dissolved_oxygen、cod、bod、nitrate、chlorophyll、pahs；
- app.py 已清理重复函数和常量，页面标题统一为“环境监测数据质控与分析工具”；
- 综合工作簿逐变量生成，并在 `processing_status` 中记录数据来源、时间范围、自动质控状态、人工确认状态和跳过原因；
- 当前变量使用人工确认后的 final_qc_data；其他变量仅完成自动质控，导出中会明确标记；
- 月平均和月标准差 Plotly 图已按注册表通用生成；
- 变量配置见 `docs/V3_VARIABLE_CONFIG.md`；PAHs 单位已确认，为 `ppb`。

# 下一步

- 运行 `src/v3_4_release_validation.py` 和既有 V2/V3 回归脚本；
- 测试通过后按用户要求保存本地 Git 版本；
- V4 再开始调和分析。

# 当前禁止

- 不实现调和分析；
- 不实现自动报告；
- 不修改 V2 QC 算法、人工决策逻辑、统计口径或日内距平定义。
