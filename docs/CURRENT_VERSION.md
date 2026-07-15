# V4.1.1 时间变化正文重构与最终保存

- 第3章的 hourly、intraday、monthly 三段综合分析已固定置于图2、图3、图4之前。
- 月平均多阶段识别、周期识别和结论生成已完成，真实 PAHs、水深、温度、盐度和 BOD 报告已做抽查，正文与图件未见明显冲突。

# V4.1.1 单变量自动报告完成

- 当前版本为 V4.1.1，单变量 Word 自动报告已完成。
- 报告基于本地确定性规则生成，不依赖大模型或外部 API。
- 已实现小时、日内距平、月平均三层描述，以及月平均多阶段识别和周期识别。
- 温度单位已统一为 `℃`，并同步用于页面、图轴、表格、Word 和 Excel 导出。
- 报告仅使用已确认的 `final_qc_data`、`final_qc_log`、`qc_summary`、`review_table`、`resampled`、`anomaly` 和 `metrics`。

# V4.1.1 交接结论

- 单变量 Word 报告已达到求职项目展示和后续开发基础要求。
- 当前版本尚未完成多变量综合 Word 报告。
- 后续开发优先进入 V4.2 多变量报告，或转入 V5 产品化整理。

# 当前版本说明

## 当前版本

当前版本：V4.1.1 单变量自动报告最终保存版。

## 已完成

- V3.1 通用变量架构；
- V3.2 接入 salinity、dissolved_oxygen、cod；
- V3.2.1 完成 hard_range 与候选图保极值背景线；
- V3.3 接入 bod、nitrate、chlorophyll、pahs，并完成全变量回归；
- V3.4 清理 app.py 重复定义，补充通用月统计图、逐变量综合导出状态、全变量验收和用户文档；
- V4.1.1 完成单变量 Word 自动报告、时间变化正文重构、月平均多阶段识别和周期识别。

当前支持变量：depth、temperature、salinity、dissolved_oxygen、cod、bod、nitrate、chlorophyll、pahs。

## 当前已知问题

- PAHs 单位已由项目确认，为 `ppb`；
- BOD、nitrate、PAHs 的 `hard_max=100` 是项目宽松暂定值；chlorophyll 的 `hard_max=100` 是基于当前样例分布确定的项目操作性上限，不是通用物理上限；
- 调和分析仍属于后续 V4 规划，自动报告以外的多变量综合 Word 报告尚未完成。

## 下一步

- 运行 V4.1.1 轻量回归并保留本地 Git 标签；
- 如需继续产品化，进入 V4.2 多变量报告；
- 如需面向交付，再进入 V5 整理与发布准备。
