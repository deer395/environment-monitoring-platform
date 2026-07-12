# V3 通用多变量架构审计

## 审计范围

本次审计面向 V3 通用多变量版本开始前的架构准备，仅阅读现有代码，不修改 Python 文件、不修改质控算法、不新增变量、不执行提交或推送。

重点审计文件：

- `app.py`
- `src/variable_registry.py`
- `src/loaders.py`
- `src/qc.py`
- `src/manual_qc.py`
- `src/metrics.py`
- `src/resampling.py`
- `src/plotting.py`
- `src/report_tables.py`
- 所有 preview/test 脚本

当前分支检查结果：`feature/v3-general-variables`

## 1. 仍硬编码 depth 或 temperature 的模块

### app.py

当前仍存在明显的 V2 双变量假设：

- `DEFAULT_FILES = {"depth": ..., "temperature": ...}`
- 侧边栏固定提供水深和温度两个上传入口
- 当前上传文件选择使用 `depth_upload if variable_key == "depth" else temp_upload`
- 综合工作簿导出固定遍历 `{"depth": depth_upload, "temperature": temp_upload}`
- 导出表固定写入 `temperature_monthly` 和 `depth_daily_range`
- 分析展示中使用 `if variable_key == "temperature"`，否则按水深处理
- `_run_after_qc()` 对所有变量都执行 hourly、daily、日内距平和 `calculate_metrics`

### src/loaders.py

- `load_depth_and_temperature()` 明确只读取 `depth.xls` 和 `temp.xls`
- preview 脚本大量依赖该函数
- 默认数据路径仍假设每个变量有独立 Excel 文件

### src/metrics.py

- `calculate_metrics()` 按 `variable_key == "temperature"` 和 `variable_key == "depth"` 分发
- 新增变量会直接触发 `Unsupported V1 variable`
- `daily_range` 强依赖日内距平
- `monthly` 统计只在 temperature 分支中生成

### src/report_tables.py

- 已有基础统计表较通用
- 但仍有专用函数：
  - `build_temperature_monthly_table`
  - `build_depth_daily_range_table`
- `export_summary_statistics()` 固定写入 `temperature_monthly` 和 `depth_daily_range`

### src/plotting.py

- 基础时序图、距平图和 QC 图可复用
- 但月统计图函数仍是 `plot_temperature_monthly`
- 当前图件类型没有完全由 registry 驱动

### Preview/Test 脚本

以下脚本仍明显围绕 depth 和 temperature：

- `src/pipeline_preview.py`
- `src/plot_preview.py`
- `src/export_preview.py`
- `src/v2_stage1_preview.py`
- `src/v2_stage2_preview.py`
- `src/v2_stage3_preview.py`
- `src/v2_stage4_preview.py`

主要问题：

- 多数脚本调用 `load_depth_and_temperature()`
- 多数脚本默认对所有变量运行 hourly/daily/anomaly
- 输出文件名仍固定包含 depth 和 temperature
- 导出表仍固定包含 temperature monthly 和 depth daily range

## 2. 当前新增一个变量需要修改哪些文件

如果现在新增一个普通变量，例如 salinity，至少需要修改：

- `src/variable_registry.py`：新增变量元数据、单位、别名、范围、QC 参数、统计和图件配置
- `app.py`：新增上传入口、默认文件映射、当前变量上传文件选择逻辑、综合导出逻辑、变量专属展示逻辑
- `src/loaders.py`：如果继续使用默认批量读取，需要扩展 `load_depth_and_temperature()` 或新增通用 loader
- `src/metrics.py`：新增变量统计分支，否则会报不支持
- `src/report_tables.py`：如果有变量专属统计，需要新增表构建函数和导出 sheet
- `src/plotting.py`：如果有新图件类型，需要新增绘图函数或通用绘图入口
- preview 脚本：需要扩展默认数据读取、输出路径和断言逻辑
- 文档：需要更新 schema、scope、验收标准或示例

这说明当前项目还没有达到“新增变量主要只修改 variable_registry.py”的 V3 目标。

## 3. 可以通用的统计指标

以下统计指标适合作为通用基础指标：

- 观测开始时间
- 观测结束时间
- 原始记录数
- 缺测数
- 有效记录数
- mean
- max
- min
- std
- QC 摘要
- QC 日志统计

这些指标只依赖标准化后的 `datetime` 和 `value`，适合大部分单变量时间序列。

## 4. 必须按变量配置的统计指标

以下统计不应默认对所有变量执行，应由 registry 配置控制：

- monthly_mean
- monthly_std
- hourly_mean
- daily_mean
- 日内距平
- daily_range
- max_daily_range
- 调和分析相关指标
- 低频监测变量的批次统计
- 多站点汇总
- 多水层汇总
- 超标率、达标率或环境标准相关指标

原因是不同变量的采样频率、物理意义和报告口径不同。COD、BOD 等低频变量不应默认运行日内距平或日变化幅度。

## 5. Hampel 是否真正使用滚动中位数和 MAD

结论：是。

`src/qc.py` 中 `detect_hampel_candidates()` 使用：

- `values.rolling(window=window, center=True, min_periods=3)`
- `rolling.median()`
- 自定义 `mad(series)`，计算窗口内 `abs(value - median)` 的中位数
- 阈值为 `sigma * 1.4826 * MAD`
- 支持 `hampel_min_abs_deviation` 作为最小绝对偏差阈值

需要注意：

- 当前窗口按记录数滚动，不是按真实时间跨度滚动
- 不规则采样下，窗口代表“附近若干条记录”，不是固定小时数
- MAD 为 0 的窗口不会标记
- Hampel 默认只标记，不自动删除

## 6. constant_value 是否独立于 Hampel

结论：是。

`detect_constant_value_candidates()` 是独立函数：

- 使用 `constant_value_window`
- 使用 `constant_value_tolerance`
- 检测连续值完全相同或变化小于容差的长段
- 生成 `constant_value` 规则日志
- 默认只标记，不自动删除

它不依赖 Hampel 的输出，也没有被 Hampel 替代。

## 7. 当前能力支持情况

### 不同单位

部分支持。

- 单位来自 `variable_registry.py`
- resampling、plotting、report table 可以携带和显示单位
- 但单位换算、同类变量不同单位兼容尚未支持

### 不同采样频率

部分支持。

- pandas resample 可以处理不同时间间隔的数据
- 但当前流程默认所有变量都执行 hourly 和 daily
- registry 中虽然有 `resampling` 字段，但 app 和 preview 尚未完全按配置分发

### 不规则采样

部分支持。

- loader 会排序时间
- resample 能将不规则采样聚合到小时/日
- 但缺少覆盖率、最小样本数、时间间隔诊断
- Hampel 是按记录窗口，不是按时间窗口

### 多站点

暂不支持。

- loader 只保留 `datetime` 和 `value`
- station 字段会被丢弃
- record_id 仅区分行，不代表站点分组
- QC、resampling、metrics 都未按 station 分组

### 多水层

暂不支持。

- loader 只保留一个 value 列
- layer/depth_level 字段会被丢弃
- QC、resampling、metrics 都未按水层分组

## 8. COD、BOD 等低频变量的误运行风险

当前如果把 COD、BOD 等低频变量直接加入 registry，并让 app 走现有流程，会有明显风险。

### 小时重采样

会被执行。

`app.py` 的 `_run_after_qc()` 对所有变量调用 `resample_hourly_mean()`。低频变量会产生大量空小时，统计和图件可能误导用户。

### 日内距平

会被执行。

`_run_after_qc()` 对所有变量调用 `calculate_intraday_anomaly()`。COD、BOD 等低频变量通常没有日内周期解释，运行日内距平不合理。

### 日变化幅度

可能被错误触发或无法计算。

当前 `daily_range` 只在 depth 的 metrics 分支中计算；如果未来简单复制分支，低频变量可能被错误计算日内距平 range。V3 必须通过 registry 的指标能力控制，低频变量默认禁用日内距平和日变化幅度。

## 9. 为实现“新增变量主要只修改 variable_registry.py”必须重构的模块

### app.py

需要从“双变量页面”改为“变量配置驱动页面”：

- 上传控件按 registry 动态生成
- 默认文件按 registry 读取
- 分析流程按变量能力执行
- 显示区域按变量 plots 和 metrics 配置生成
- 多变量导出不再固定 depth/temperature
- session_state 需要按 variable_key 分区管理

### src/loaders.py

需要新增通用批量加载入口：

- 根据 registry 遍历启用变量
- 支持可选文件、默认文件和上传文件
- 保留可选字段，如 station、layer
- 不再依赖 `load_depth_and_temperature()`

### src/metrics.py

需要从变量名分发改为指标名分发：

- 通用 scalar metrics
- 可配置 monthly metrics
- 可配置 anomaly-based metrics
- 可配置 low-frequency metrics
- 指标函数应由 registry 的 `metrics` 列表决定

### src/resampling.py

需要支持配置驱动：

- resampling frequency
- aggregation method
- min_count 或 coverage
- 是否跳过 hourly
- 是否跳过 daily

### src/anomaly.py

需要变成可选能力：

- 只有 registry 明确配置 anomaly 时才执行
- 低频变量默认不执行
- 可支持不同 anomaly 定义

### src/report_tables.py

需要通用导出：

- 不再固定 `temperature_monthly`
- 不再固定 `depth_daily_range`
- 根据每个变量实际生成的指标表动态写 sheet
- 支持多变量汇总表

### src/plotting.py

需要通用绘图入口：

- 根据 plot type 分发
- 根据 registry 控制 y 轴、单位、标题、图件是否启用
- 月统计图不应绑定 temperature

### Preview/Test 脚本

需要从 V1/V2 专用脚本过渡为：

- 通用变量 smoke test
- depth/temperature 回归测试
- 新变量配置测试
- 低频变量不执行日内距平的测试

## 10. Plotly、缓存、session_state 的多变量风险

### Plotly 风险

- 大数据量多变量同时展示会增加前端渲染压力
- 当前 `Scattergl` 对单变量长序列可用，但多变量同时显示可能卡顿
- 多变量候选点叠加后 hover 和选择可能变复杂
- 需要限制默认显示时间范围、抽样预览或分页

### 缓存风险

- 当前缓存键包含上传文件 hash、变量、时间范围、QC 开关和 QC 参数
- 对单变量有效
- V3 中 registry 配置变化、变量启用状态、多站点/多水层筛选也应进入缓存键
- 大量变量上传后，缓存内存占用可能上升

### session_state 风险

- 当前主要保存当前变量的 `review_table`、`selected_record_ids`、`final_qc_data` 和 `qc_confirmed`
- 多变量下需要按 variable_key 管理状态
- 否则可能出现一个变量的人工决策污染另一个变量
- 多站点/多水层下还需要按 station/layer 管理状态
- 下载综合工作簿时，需要明确哪些变量已人工确认，哪些只是自动质控

## 11. V3 建议拆分

### V3.1 通用变量架构

目标是先打通配置驱动骨架，不急于新增大量变量。

重点：

- 定义变量能力模型
- 改造 loader、pipeline、metrics、plots 的分发方式
- 保留 depth 和 temperature 回归结果

### V3.2 新变量配置

目标是新增少量代表性变量，验证 registry 是否足够表达不同变量。

建议顺序：

1. salinity：高频、类似 temperature
2. dissolved oxygen：可能有日变化，但统计口径不同
3. pH、turbidity、chlorophyll：中高频变量
4. COD、BOD：低频变量，用来验证跳过 hourly/anomaly/daily_range

### V3.3 通用统计与绘图

目标是把统计表和图件从变量名硬编码中解耦。

重点：

- 指标函数按 metric name 注册
- 图件函数按 plot type 注册
- 导出 sheet 动态生成
- 低频变量只输出适合它的统计和图件

### V3.4 多变量界面与回归测试

目标是让用户能在一个界面中管理多个变量，并保证 V2 行为不被破坏。

重点：

- 多变量上传和状态管理
- 多变量 QC 状态摘要
- 多变量汇总导出
- depth/temperature 回归测试
- 低频变量防误运行测试

## 模块改造总表

| 模块 | 当前状态 | 主要问题 | V3 改造建议 | 优先级 |
|---|---|---|---|---|
| `app.py` | V2 单变量交互可用，但围绕 depth/temperature | 上传、默认文件、导出、展示和状态管理仍有双变量假设 | 改为 registry 驱动的变量列表、上传、分析流程和状态分区 | 高 |
| `src/variable_registry.py` | 已包含 depth/temperature 元数据和部分能力字段 | 字段尚未成为流程控制的唯一来源；部分中文字符串存在编码可维护性风险 | 扩展为变量能力模型，明确 resampling、anomaly、metrics、plots、frequency、grouping | 高 |
| `src/loaders.py` | 单变量 Excel loader 较通用 | 批量 loader 固定 depth/temperature；不保留 station/layer | 新增通用多变量 loader，支持可选分组字段 | 高 |
| `src/qc.py` | physical_range、Hampel、constant_value 可用 | rate_change 仍是占位；Hampel 按记录窗口不是时间窗口 | 保持现有规则，增加配置化启用和时间窗口选项 | 中 |
| `src/manual_qc.py` | record_id 决策链路可用 | 状态模型适合单变量；部分展示字符串编码不稳定 | 决策表支持 variable/station/layer 组合键 | 中 |
| `src/metrics.py` | depth/temperature 指标可用 | 按变量名硬编码，新增变量必改代码 | 改为 metric registry，按指标名执行 | 高 |
| `src/resampling.py` | hourly/daily mean 可用 | 所有变量默认 hourly/daily，缺少配置和覆盖率 | 支持按变量配置频率、聚合方法和跳过策略 | 高 |
| `src/anomaly.py` | 日内距平定义清晰 | 当前容易被所有变量误用 | 变成可选指标能力，仅配置后执行 | 高 |
| `src/plotting.py` | 基础图和 QC 图可复用 | 月统计图绑定 temperature，图件未完全按 plot type 配置 | 建立 plot type 分发和统一主题入口 | 中 |
| `src/report_tables.py` | 基础统计和 QC 日志较通用 | 专用 monthly/daily_range sheet 仍硬编码 | 动态生成 per-variable 和 per-metric sheet | 高 |
| Preview 脚本 | 可验证 V1/V2 流程 | 全部围绕 depth/temperature，默认执行 hourly/anomaly | 拆成通用 smoke test、回归测试、低频变量防误运行测试 | 中 |
| `docs/` | 已有路线图和版本说明 | V3 技术拆分尚未沉淀到实施任务 | 用本审计文档作为 V3.1 输入 | 中 |

## 子阶段实施表

| 子阶段 | 目标 | 修改文件 | 验收条件 | 风险 |
|---|---|---|---|---|
| V3.1 通用变量架构 | 建立配置驱动的变量能力模型 | `variable_registry.py`, `loaders.py`, `app.py`, `resampling.py`, `anomaly.py` | 新增一个普通高频变量时，主要改 registry；depth/temperature 结果保持一致 | 改动面大，容易影响 V2 已验证流程 |
| V3.2 新变量配置 | 加入代表性变量验证架构 | `variable_registry.py`, 示例数据 schema 文档, preview 脚本 | salinity 可运行；COD/BOD 可加载但不会误跑日内距平 | 真实数据字段差异可能超出别名配置 |
| V3.3 通用统计与绘图 | 消除 metrics/report/plot 的变量名分支 | `metrics.py`, `report_tables.py`, `plotting.py`, `app.py` | 指标和图件按 registry 配置生成；动态导出 sheet | 指标口径不清会导致结果解释混乱 |
| V3.4 多变量界面与回归测试 | 支持多变量状态、导出和回归验证 | `app.py`, preview/test 脚本, docs | 多变量 QC 状态互不污染；depth/temperature 回归通过；低频变量不运行错误流程 | session_state 和缓存键复杂度上升 |

## 三个最高优先级问题

1. `app.py` 仍是 depth/temperature 双变量界面和流程，不具备通用变量状态管理能力。
2. `src/metrics.py` 仍按变量名硬编码，新增变量必须改代码，且低频变量有误运行日内距平相关流程的风险。
3. `src/loaders.py` 和 preview 脚本仍依赖 `load_depth_and_temperature()`，新增变量无法只靠 registry 进入完整验证链路。
