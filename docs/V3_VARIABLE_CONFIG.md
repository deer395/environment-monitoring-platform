# V3 变量配置

所有显示名称、单位、默认文件、硬范围和 QC 参数均由 `src/variable_registry.py` 提供。硬范围命中的记录自动置为缺测，且不能通过人工恢复。当前九个变量均启用 `zero_is_invalid=True`：仅精确 `0.0` 按传感器无效值规则 `sensor_zero` 自动删除，不改变 hard_min 的边界含义。

| variable_key | 中文名称 | 英文名称 | 单位 | 默认文件 | hard_min | hard_max | 上限性质 | 是否已确认 | 备注 |
| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| depth | 水深 | Depth | m | depth.xls | 0 | 100 | 项目宽松硬范围 | 暂定 | 后续可按仪器量程调整。 |
| temperature | 温度 | Temperature | degC | temp.xls | -2.5 | 50 | 项目宽松硬范围 | 暂定 | 后续可按仪器量程调整。 |
| salinity | 盐度 | Salinity | PSU | 盐度.xls | 0 | 50 | 项目宽松硬范围 | 暂定 | 后续可按仪器量程调整。 |
| dissolved_oxygen | 溶解氧 | Dissolved Oxygen | mg/L | 溶解氧.xls | 0 | 100 | 项目宽松硬范围 | 暂定 | 后续可按仪器量程调整。 |
| cod | 化学需氧量 | Chemical Oxygen Demand | mg/L | COD.xls | 0 | 100 | 项目宽松硬范围 | 暂定 | 后续可按仪器量程调整。 |
| bod | 生化需氧量 | Biochemical Oxygen Demand | mg/L | BOD.xls | 0 | 100 | 项目宽松暂定值 | 未确认 | `hard_max=100` 不是通用物理上限。 |
| nitrate | 硝酸盐 | Nitrate | mg/L | 硝酸盐.xls | 0 | 100 | 项目宽松暂定值 | 未确认 | `hard_max=100` 不是通用物理上限。 |
| chlorophyll | 叶绿素 | Chlorophyll | ug/L | 叶绿素.xls | 0 | 100 | 项目操作性上限 | 已按当前样例确认 | 基于当前样例分布确定，不是所有海域和仪器通用的物理上限。 |
| pahs | 多环芳烃 | Polycyclic Aromatic Hydrocarbons | ppb | 多环芳烃.xls | 0 | 100 | 项目宽松暂定值 | 已确认 | 项目已确认单位为 ppb。 |

获得仪器量程或现场资料后，应只在注册表中更新相应配置，并重新执行全变量验收。
