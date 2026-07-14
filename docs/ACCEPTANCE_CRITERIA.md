# 验收标准

## V2

- hard_range 自动处理且不可恢复；
- Hampel 与 constant_value 默认只标记；
- 人工删除、保留和恢复可追溯到 QC 日志；
- 后续重采样、统计、绘图和导出只使用 final_qc_data；
- 原始 Excel 文件不被修改。

## V3

- 新增普通变量主要通过 `src/variable_registry.py` 和别名配置完成；
- app.py、metrics.py、loaders.py 不按变量名称复制分析主流程；
- 所有已支持变量执行小时平均、日平均、日内距平、日变化幅度、月统计、图表和导出；
- session_state 按 variable_key 隔离；
- depth 和 temperature 保持回归通过。

## V3.4

- app.py 中每个运行时函数和常量只保留一个有效定义；
- 九个已支持变量均可完成 Excel 读取、hard_range、候选标记、人工复核、final_qc_data、统计、图件和表格导出；
- 综合工作簿逐变量生成并包含 processing_status，缺失或空变量不阻断其他变量导出；
- 导出明确区分人工确认和仅自动质控；
- PAHs 单位为项目确认的 `ppb`；
- 所有 Python 文件通过 AST 语法解析，V2、V3.1、V3.2、V3.3 和 V3.4 回归脚本通过。
