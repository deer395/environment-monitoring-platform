# V4.2 站点任务与综合报告交接

## 当前阶段：月际报告质量评估 baseline

- V4.2 冻结基线：`abdff0bc249a4707949515ab614afc707be4fcd9` / `v4.2-station-report-complete`。
- 当前分支：`feature/report-quality-evaluation`；仅新增评估工具和文档，未修改月际算法。
- 评估流程：使用私有工作簿生成盲图、人工参考标注和 V4.2 baseline；当前覆盖 27 个样本，development 18 个、holdout 9 个。holdout 仅用于最终验证，不得参与规则调参。
- 结论：无主要趋势或核心阶段重大错误；待处理的问题是部分月际文字过度拆分。下一阶段只做阶段压缩和叙述合并，不修改统计值、关键月份、质控流程或 Word 结构。
- 隐私：`evaluation_input_private/`、清单、盲图、标注表、baseline 输出和人工评价结果均不得提交。

## 启动方式

- 安装依赖：`pip install -r requirements.txt`
- 启动页面：`streamlit run app.py`

## 当前核心流程

1. 填写全局站点任务信息。
2. 逐一上传九个变量 Excel 文件。
3. 对每个变量运行自动质控并完成人工复核。
4. 所有候选记录必须明确删除或保留后，才能确认最终质控结果。
5. 后续统计、绘图、Excel 和 Word 报告均使用有效确认后的 `final_qc_data`。
6. 九变量全部有效确认后，才允许生成站点综合 Excel 和站点综合 Word。

## 关键模块

- `app.py`：Streamlit 页面编排、状态调用和导出入口。
- `src/station_task.py`：站点信息、九变量状态汇总、严格导出门槛和报告缓存清理。
- `src/station_report_context.py`：基于九变量 `confirmed_qc_assets` 构建站点综合报告上下文。
- `src/station_word_report.py`：生成站点综合 Word。
- `src/report_context.py` 与 `src/word_report.py`：单变量确定性报告上下文与 Word 报告。
- `src/manual_qc.py`：人工复核决定与候选记录统计。
- `src/variable_registry.py`：九个固定变量的中文名、单位和质控参数。

## 已完成报告

- 单变量 Word 报告继续可用。
- 站点综合 Excel 已按严格九变量确认门槛生成。
- 站点综合 Word 已包含：
  - 站点数据与质控汇总；
  - 两张多要素日平均总览图；
  - 九个监测要素详细分析章节。

## 当前限制

- 不进行调和分析。
- 不接入大模型完成核心事实判断。
- 不自动读取 `data_private/` 作为正式站点任务数据源。
- 报告解读质量评估尚未实施，下一阶段从 `feature/report-quality-evaluation` 开始。

## 测试

- 全量测试命令：`python -m pytest tests -q -p no:cacheprovider`
- 当前结果：`23 passed`。
