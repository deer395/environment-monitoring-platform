# V4.1.1 时间变化交接

- `report_context` 提供分离的 hourly、intraday、monthly、conclusion 叙述字段，Word 按固定顺序渲染。
- 单变量 Word 报告已完成时间变化正文重构，小时、日内距平和月平均三层描述均为本地确定性生成。

# V4.1.1 模式与阶段交接

- `time_series_interpretation.py` 提供可复现的月平均多阶段识别和周期特征提取。
- `src/word_report.py` 仅消费已确认资产与这些特征，生成质控、统计和结论文字，不重新运行 QC 或统计。
- 报告正文不显示重复时间说明，不依赖大模型或外部 API。

# V4.1.1 启动与使用

- 启动依赖：`pip install -r requirements.txt`
- Streamlit 启动：`streamlit run app.py`
- 数据放置：将 Excel 文件放入 `data_private/`，或在界面中选择注册表对应的默认样例文件。
- 主要功能：Excel 读取、质量控制、人工复核、小时平均、日平均、日内距平、月平均、统计分析、绘图、Excel 导出和单变量 Word 报告。

# V4.1.1 当前限制

- 当前仅完成单变量 Word 自动报告，多变量综合 Word 报告尚未完成。
- 调和分析仍属于后续版本规划。
- 报告仅基于已确认的 `final_qc_data` 和相关派生结果生成。

# V4.1.1 后续入口

- 后续开发优先进入 V4.2 多变量报告。
- 如果转向产品化整理，则进入 V5 任务。

# 当前分支

feature/v3-general-variables

# 当前已完成

- V2 质量控制闭环；
- V3.1 通用变量架构；
- V3.2 接入 salinity、dissolved_oxygen、cod；
- V3.2.1 完成 hard_range 与候选图背景线修复；
- V3.3 接入 bod、nitrate、chlorophyll、pahs；
- V3.4 完成最终验收、导出可靠性修复和文档收尾；
- V4.1.1 完成单变量 Word 自动报告、月平均多阶段识别、周期识别和结论生成。

# 当前 Git 基线

- `v2-qc-complete`
- `v3.1-generic-architecture`
- `v3.2-three-variable-validation`
- `v3.2.1-qc-interaction-complete`
- `v3.3-all-variables-complete`

# V3.4 / V4.1.1 说明

- 当前支持九个变量：depth、temperature、salinity、dissolved_oxygen、cod、bod、nitrate、chlorophyll、pahs；
- app.py 已清理重复函数和常量，页面标题统一为“环境监测数据质控与分析工具”；
- 综合工作簿逐变量生成，并在 `processing_status` 中记录数据来源、时间范围、自动质控状态、人工确认状态和跳过原因；
- 温度单位已统一为 `℃`，并同步到页面、图轴、表格、Word 和 Excel；
- 月平均和月标准差 Plotly 图已按注册表通用生成；
- 变量配置见 `docs/V3_VARIABLE_CONFIG.md`；PAHs 单位已确认，为 `ppb`。

# 下一步

- 若继续功能扩展，进入 V4.2 多变量报告；
- 若继续收尾，进入 V5 产品化整理与发布准备。

# 当前禁止

- 不实现调和分析；
- 不实现自动报告；
- 不修改 V2 QC 算法、人工决策逻辑、统计口径或日内距平定义。
