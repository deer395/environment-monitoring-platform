# 环境监测数据质控与分析平台

> 面向环境监测时序数据的一站式质控、统计与报告工具 —— 三步质控、确定性计算、一键生成 Word 报告。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-交互界面-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Plotly-可视化-3F4F75?style=for-the-badge&logo=plotly&logoColor=white" alt="Plotly">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

---

## 在线体验（无需安装）

**打开即用，一行代码都不用写：**

👉 **[https://marine-monitoring-qc.streamlit.app/](https://marine-monitoring-qc.streamlit.app/)**

应用已部署在 Streamlit Cloud，打开后选择变量、上传 Excel 文件，即可体验完整的质控与分析流程。

> 💡 **没有数据？** 仓库 [`demo_data/`](demo_data/) 目录提供了 9 种变量的脱敏示例数据，下载后上传即可快速上手。

---

## 它解决什么问题

环境监测数据在分析前，总要经过一段繁琐又容易出错的「脏活」：识别缺测、剔除超范围异常、人工复核可疑值、再算统计、画图、写报告。传统方式往往是**多套工具来回切换、口径不一、报告全靠手工拼**。

这个平台把整条链路收进一个页面：

```
上传 Excel → 自动质控 → 人工复核 → 统计分析 → 一键导出 Word 报告
```

**核心设计原则：所有数值计算由确定性 Python 代码完成，AI 只负责基于已算好的结果生成报告文字，绝不参与数值计算或机理推断。** 这意味着结果可复现、可追溯、可信赖。

---

## 核心特性

### 📥 数据加载

- 支持 Excel 文件读取，兼容多种时间列别名（`datetime`、`time`、`日期时间`、`监测时间`）
- 源文件**只读**，原始数据永不被修改
- 自动规范化为统一结构：`datetime`、`value`、`variable`、`unit`、`record_id`

### 🛡 三步质控流程

| 阶段 | 说明 |
| --- | --- |
| **① 自动质控** | 传感器精确零值（`sensor_zero`）与超范围值（`hard_range`）自动标记为缺测，不可恢复 |
| **② 人工复核** | Hampel 异常值、连续恒定值仅标记不删除；支持单点、框选、套索选择，可删除、保留或恢复任意数据点 |
| **③ 确认与分析** | 确认后的 `final_qc_data` 锁定，作为所有下游计算的唯一数据源 |

### 📊 统计与时序分析

- **基础统计**：最大值、最小值、平均值、中位数、标准差、有效记录数、缺测数
- **时序结果**：小时平均、日平均、日内距平、日变化幅度、月平均、月标准差

### 📈 可视化

- 质控摘要图、候选异常图、最终质控数据图
- 时序趋势 / 日内变化 / 月度变化 / 统计指标四个视图

### 📄 一键报告导出

- 单变量分析结果 Excel
- 含 `processing_status` 工作表的多变量综合工作簿
- **`.docx` 格式 Word 报告**（含项目名称、标题、编制单位、编制人），可直接交付

### 🧩 支持 9 种变量

| 变量 | 中文名 | 单位 | 变量 | 中文名 | 单位 |
| --- | --- | --- | --- | --- | --- |
| `depth` | 水深 | m | `cod` | 化学需氧量 | mg/L |
| `temperature` | 温度 | ℃ | `bod` | 生化需氧量 | mg/L |
| `salinity` | 盐度 | psu | `nitrate` | 硝酸盐 | mg/L |
| `dissolved_oxygen` | 溶解氧 | mg/L | `chlorophyll` | 叶绿素 | μg/L |
| | | | `pahs` | 多环芳烃 | ppb |

变量显示名称、单位、默认文件、范围与质控参数统一配置在 `src/variable_registry.py`，一处维护、全局生效。

---

## 本地运行

如需在本地运行：

```bash
git clone https://github.com/deer395/environment-monitoring-platform.git
cd environment-monitoring-platform
pip install -r requirements.txt
streamlit run app.py
```

浏览器打开 Streamlit 显示的本地地址，选择变量并上传 Excel 文件（或使用变量注册表里配置的默认样例文件）即可开始。

### Excel 输入格式

每个文件至少包含**时间列**和**数值列**：

- 时间列别名：`datetime`、`time`、`日期时间`、`监测时间`
- 数值列：由变量注册表中的别名配置自动识别

---

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 界面框架 | Streamlit |
| 可视化 | Plotly + Matplotlib |
| 数据处理 | pandas + NumPy |
| 文件读写 | openpyxl + xlrd |
| 报告生成 | python-docx |

---

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
│   ├── station_task.py            # 站点分析任务
│   ├── station_word_report.py     # 分站点报告
│   ├── variable_registry.py       # 统一变量配置
│   ├── resampling.py              # 时序重采样
│   └── version.py                 # 版本信息
├── tests/                         # 单元与集成测试
├── evaluation/                    # 评估数据集与盲注标注
├── docs/                          # 架构与设计文档
├── demo_data/                     # 脱敏示例数据
├── requirements.txt
└── LICENSE
```

---

## 当前限制

- PAHs 单位为 `ppb`
- BOD、nitrate、PAHs、chlorophyll 的 `hard_max=100` 为项目级操作性上限，非通用物理上限
- 调和分析与自动报告功能属于后续规划范围

---

## License

MIT License — 详见 [LICENSE](LICENSE) 文件。
