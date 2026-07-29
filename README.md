# 环境监测数据质控与分析平台

> AI 辅助环境监测数据质量控制、统计分析与 Word 报告生成工具，基于 Streamlit + Python 构建。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B)](https://streamlit.io/)

## 在线体验

**直接使用，无需安装：**

👉 **[https://marine-monitoring-qc.streamlit.app/](https://marine-monitoring-qc.streamlit.app/)**

已部署在 Streamlit Cloud，打开即可使用。选择变量、上传 Excel 文件（或使用内置示例数据），即可体验完整质控与分析流程。

## 项目概览

本工具面向环境监测时序数据，为研究人员和分析人员提供一站式的数据质控、统计分析和报告生成能力。核心设计原则：**所有数值计算由确定性 Python 代码完成，AI 仅用于基于已计算结果生成报告文字描述，不参与数值计算或机理推断。**

## 功能特性

### 数据加载
- 支持 Excel 文件读取，兼容多种时间列别名（`datetime`、`time`、`日期时间`、`监测时间`）
- 源文件只读，原始数据不会被修改
- 统一内部结构：`datetime`、`value`、`variable`、`unit`、`record_id`

### 三步质控流程

| 阶段 | 说明 |
|------|------|
| **① 自动质控** | 传感器精确零值（`sensor_zero`）和超范围值（`hard_range`）自动标记为缺测，不可恢复 |
| **② 人工复核** | Hampel 异常值和恒定值标记；支持单点、框选、套索选择，可删除、保留或恢复任意原始数据点 |
| **③ 确认与分析** | 确认后的 `final_qc_data` 锁定，用于所有下游计算 |

### 分析与输出
- **基础统计**：最大值、最小值、平均值、中位数、标准差、有效记录数、缺测数
- **时序结果**：小时平均、日平均、日内距平、日变化幅度、月平均、月标准差
- **质控可视化**：QC 摘要图、候选异常图、最终质控数据图
- **数据导出**：
  - 单变量分析结果
  - 含 `processing_status` 工作表的多变量综合工作簿
  - `.docx` 格式 Word 报告（含项目名称、标题、编制单位、编制人）

### 支持变量（共 9 种）
`depth`、`temperature`、`salinity`、`dissolved_oxygen`、`cod`、`bod`、`nitrate`、`chlorophyll`、`pahs`

变量显示名称、单位、默认文件、范围和 QC 参数统一配置在 `src/variable_registry.py`。

## 项目结构

```
environment-monitoring-platform/
├── app.py                         # Streamlit 入口
├── src/
│   ├── loaders.py                 # Excel 加载与校验
│   ├── anomaly.py                 # 异常检测算法
│   ├── metrics.py                 # 统计计算
│   ├── qc.py                      # 质控流程编排
│   ├── manual_qc.py               # 交互式质控 UI
│   ├── plotting.py                # 时序与质控可视化
│   ├── report_text.py             # AI 辅助报告文字生成
│   ├── report_tables.py           # 统计表格生成
│   ├── report_context.py          # 报告数据上下文
│   ├── word_report.py             # 旧版 Word 报告导出
│   ├── station_word_report.py     # 分站点报告
│   ├── station_report_context.py  # 站点级报告数据
│   ├── station_task.py            # 站点分析任务
│   ├── variable_registry.py       # 统一变量配置
│   ├── output_paths.py            # 输出路径管理
│   ├── resampling.py              # 时序重采样
│   ├── time_series_interpretation.py  # 时序模式分析
│   └── version.py                 # 版本信息
├── tests/                         # 单元与集成测试
├── evaluation/                    # 评估数据集与盲注标注
│   └── monthly/                   # 月度评估框架
├── docs/                          # 架构与设计文档
├── scripts/                       # 工具脚本
├── requirements.txt
└── LICENSE
```

## 本地运行

如果需要在本地运行：

```bash
git clone https://github.com/deer395/environment-monitoring-platform.git
cd environment-monitoring-platform
pip install -r requirements.txt
streamlit run app.py
```

浏览器打开 Streamlit 显示的本地地址，选择变量并上传 Excel 文件，或使用变量注册表中配置的默认样例文件。

## Excel 输入格式

每个文件应至少包含时间列和数值列。通用 loader 支持以下别名：
- 时间列：`datetime`、`time`、`日期时间`、`监测时间`
- 数值列：由变量注册表中的别名配置识别

## 当前限制

- PAHs 单位已确认为 `ppb`
- BOD、nitrate、PAHs、chlorophyll 的 `hard_max=100` 为项目级操作性上限，非通用物理上限
- 调和分析和自动报告功能属于后续规划范围

## 版本历史

主要版本标签（可通过 `git tag` 查看）：

| 标签 | 说明 |
|------|------|
| `v2-qc-complete` | 完整质控流程 |
| `v3.1-generic-architecture` | 通用多变量架构 |
| `v3.2.1-qc-interaction-complete` | 交互式质控 UI 完善 |
| `v3.3-all-variables-complete` | 支持全部 9 种变量 |

查看历史版本：

```bash
git checkout v3.3-all-variables-complete
```

## License

MIT License — 详见 [LICENSE](LICENSE) 文件。