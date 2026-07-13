# 当前版本说明

## 当前版本

当前版本：V3.3 剩余变量接入与全变量回归版本

## 已完成

- V3.1 通用变量架构；
- V3.2 接入 salinity、dissolved_oxygen、cod；
- V3.2.1 完成 hard_range 分层与候选图保极值背景线；
- V3.3 接入 bod、nitrate、chlorophyll、pahs；
- 所有已支持变量统一执行 hard_range、Hampel、constant_value、人工质控、final_qc_data、小时平均、日平均、日内距平、日变化幅度、月统计、图表导出；
- 叶绿素 chlorophyll 当前采用项目级宽松 hard_range：hard_min=0、hard_max=100；
- chlorophyll 的 hard_max=100 是基于当前样本分布确定的操作性自动质控上限，不是所有海域和仪器通用的物理上限，后续可在 registry 中按仪器量程或现场资料调整。

## 当前全部已支持变量

- depth（水深）
- temperature（温度）
- salinity（盐度）
- dissolved_oxygen（溶解氧）
- cod（化学需氧量）
- bod（生化需氧量）
- nitrate（硝酸盐）
- chlorophyll（叶绿素）
- pahs（多环芳烃）

## 当前已知问题

- BOD、硝酸盐、叶绿素、多环芳烃样例文件未提供单位列，当前单位来自变量注册表；PAHs 单位仍需项目确认；
- hard_max=100 对 BOD、nitrate、chlorophyll、PAHs 是当前项目级宽松暂定值或样本决策值，后续获得仪器量程后应在 src/variable_registry.py 中调整；
- 调和分析和自动报告尚未实现。

## 下一步

- 保存 V3.3 本地 Git 版本前运行完整 V3.3 与回归测试；
- 根据仪器量程或现场资料复核各变量 hard_range；
- 进入 V4 调和分析前确认哪些变量支持调和分析。
