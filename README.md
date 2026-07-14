# 环境监测数据质控与分析工具

这是一个面向环境监测时序数据的本地工具，提供 Excel 读取、质量控制、人工复核、统计分析、绘图和结果导出。原始 Excel 文件只读，不会被修改。

## 已支持变量

`depth`、`temperature`、`salinity`、`dissolved_oxygen`、`cod`、`bod`、`nitrate`、`chlorophyll`、`pahs`。

变量显示名称、单位、默认文件、范围和 QC 参数统一配置在 `src/variable_registry.py`。详细配置见 `docs/V3_VARIABLE_CONFIG.md`。

## 三步质控流程

1. 自动规则：传感器精确 `0.0` 无效值（`sensor_zero`）和 hard_range 自动置为缺测，且不可恢复。
2. 复核：Hampel 和 constant_value 只标记；可单点、框选或套索选择任意原始点，并删除、保留或恢复。
3. 确认与分析：确认后的 `final_qc_data` 用于小时平均、日平均、日内距平、统计、绘图和导出。

日内距平定义为：小时平均值减去同一天的日平均值。

## 分析与输出

- 基础统计：最大值、最小值、平均值、中位数、标准差、有效记录数和缺测数。
- 时序结果：小时平均、日平均、日内距平、日变化幅度、月平均和月标准差。
- QC 输出：QC summary、最终 QC log、候选异常图和 final_qc_data 图。
- 导出：当前变量结果，以及带 `processing_status` 工作表的全变量综合工作簿。

综合工作簿会明确区分当前变量的人工确认结果和其他变量的“仅完成自动质控”结果；缺失变量会被跳过并记录原因。

## 安装与启动

建议使用 Python 3.10 或更高版本，并安装项目所需依赖：

```powershell
pip install pandas plotly streamlit openpyxl xlrd matplotlib
streamlit run app.py
```

浏览器打开 Streamlit 显示的本地地址后，选择变量并上传 Excel，或使用 `data_private/` 中注册表指定的默认样例文件。

## Excel 输入格式

每个文件应至少包含时间列和数值列。通用 loader 支持常见别名，例如 `datetime`、`time`、`日期时间`、`监测时间`；数值列由变量注册表中的别名识别。加载后统一结构包含 `datetime`、`value`、`variable`、`unit` 和 `record_id`。

## 当前限制

- PAHs 单位已由项目确认，为 `ppb`。
- BOD、nitrate、PAHs 的 `hard_max=100` 是项目宽松暂定值；chlorophyll 的 `hard_max=100` 是基于当前样例分布确定的项目操作性上限，均不是所有场景的通用物理上限。
- 调和分析和自动报告属于后续 V4/V5 范围，尚未实现。

## Git 版本与恢复

主要标签包括 `v2-qc-complete`、`v3.1-generic-architecture`、`v3.2-three-variable-validation`、`v3.2.1-qc-interaction-complete`、`v3.3-all-variables-complete`。查看版本：

```powershell
git tag
git show v3.3-all-variables-complete
```

在新分支基于某个标签继续工作：

```powershell
git switch -c restore-v3.3 v3.3-all-variables-complete
```
