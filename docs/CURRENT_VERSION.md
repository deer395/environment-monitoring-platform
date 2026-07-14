# 当前版本说明

## 当前版本

当前版本：V3.4 通用多变量版本最终验收与产品收尾。

## 已完成

- V3.1 通用变量架构；
- V3.2 接入 salinity、dissolved_oxygen、cod；
- V3.2.1 完成 hard_range 与候选图保极值背景线；
- V3.3 接入 bod、nitrate、chlorophyll、pahs，并完成全变量回归；
- V3.4 清理 app.py 重复定义，补充通用月统计图、逐变量综合导出状态、全变量验收和用户文档。

当前支持变量：depth、temperature、salinity、dissolved_oxygen、cod、bod、nitrate、chlorophyll、pahs。

## 当前已知问题

- PAHs 单位已由项目确认，为 `ppb`；
- BOD、nitrate、PAHs 的 `hard_max=100` 是项目宽松暂定值；chlorophyll 的 `hard_max=100` 是基于当前样例分布确定的项目操作性上限，不是通用物理上限；
- 调和分析和自动报告尚未实现，分别属于 V4 和 V5。

## 下一步

- V3.4 测试通过后保存本地 Git 版本；
- 获得仪器量程或现场资料后复核各变量范围；
- V4 开始前确认适用调和分析的变量和数据条件。
